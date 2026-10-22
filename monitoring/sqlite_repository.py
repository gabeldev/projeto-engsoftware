"""Persistência SQLite; transações protegem as regras de reserva."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from monitoring.errors import RequestStateError
from monitoring.models import (
    AppointmentSlot, Attendance, AttendanceStatus, Booking, ExceptionRequest, Feedback,
    Notification, RequestStatus,
)

class SQLiteScheduleRepository:
    def __init__(self, path: str = 'monitoring.sqlite3'):
        self.connection = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA foreign_keys = ON')
        self.connection.executescript('''
            CREATE TABLE IF NOT EXISTS slots (
                id INTEGER PRIMARY KEY,
                monitor_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                starts_at TEXT NOT NULL,
                capacity INTEGER NOT NULL CHECK(capacity > 0)
            );
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY,
                student_id INTEGER NOT NULL,
                slot_id INTEGER NOT NULL REFERENCES slots(id),
                question TEXT NOT NULL CHECK(length(trim(question)) > 0),
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'CANCELLED')),
                cancelled_at TEXT,
                cancellation_reason TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS active_booking
            ON bookings(student_id, slot_id) WHERE status = 'ACTIVE';
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS exception_requests (
                id INTEGER PRIMARY KEY,
                booking_id INTEGER NOT NULL REFERENCES bookings(id),
                requester_id INTEGER NOT NULL,
                reason TEXT NOT NULL CHECK(length(trim(reason)) > 0),
                status TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK(status IN ('PENDING', 'APPROVED', 'REJECTED')),
                created_at TEXT NOT NULL,
                decided_by INTEGER,
                decided_at TEXT,
                decision_note TEXT NOT NULL DEFAULT ''
            );
            CREATE UNIQUE INDEX IF NOT EXISTS open_exception
            ON exception_requests(booking_id) WHERE status IN ('PENDING', 'APPROVED');
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY,
                booking_id INTEGER NOT NULL UNIQUE REFERENCES bookings(id),
                student_id INTEGER NOT NULL,
                rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                comment TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY,
                booking_id INTEGER NOT NULL UNIQUE REFERENCES bookings(id),
                status TEXT NOT NULL CHECK(status IN ('PRESENT', 'ABSENT')),
                marked_by INTEGER NOT NULL,
                marked_at TEXT NOT NULL
            );
        ''')

    @contextmanager
    def transaction(self):
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @staticmethod
    def _slot(row):
        return AppointmentSlot(row['id'], row['monitor_id'], row['subject'],
                               datetime.fromisoformat(row['starts_at']), row['capacity'])

    def list_slots(self):
        return [self._slot(row) for row in self.connection.execute('SELECT * FROM slots ORDER BY id')]

    def get_slot(self, slot_id):
        row = self.connection.execute('SELECT * FROM slots WHERE id = ?', (slot_id,)).fetchone()
        if row is None:
            raise ValueError('Vaga inexistente.')
        return self._slot(row)

    def add_slot(self, monitor_id, subject, starts_at, capacity):
        cursor = self.connection.execute(
            'INSERT INTO slots(monitor_id, subject, starts_at, capacity) VALUES (?, ?, ?, ?)',
            (monitor_id, subject, starts_at.isoformat(), capacity))
        return self.get_slot(cursor.lastrowid)

    @staticmethod
    def _booking(row):
        return Booking(row['id'], row['student_id'], row['slot_id'], row['question'],
                       datetime.fromisoformat(row['created_at']), row['status'],
                       datetime.fromisoformat(row['cancelled_at']) if row['cancelled_at'] else None,
                       row['cancellation_reason'])

    def list_bookings(self):
        return [self._booking(row) for row in self.connection.execute('SELECT * FROM bookings ORDER BY id')]

    def get_booking(self, booking_id):
        row = self.connection.execute('SELECT * FROM bookings WHERE id = ?', (booking_id,)).fetchone()
        if row is None:
            raise ValueError('Reserva inexistente.')
        return self._booking(row)

    def add_booking(self, student_id, slot_id, question, created_at):
        cursor = self.connection.execute(
            'INSERT INTO bookings(student_id, slot_id, question, created_at) VALUES (?, ?, ?, ?)',
            (student_id, slot_id, question, created_at.isoformat()))
        return self.get_booking(cursor.lastrowid)

    def cancel_booking(self, booking_id, cancelled_at, reason):
        self.connection.execute(
            "UPDATE bookings SET status = 'CANCELLED', cancelled_at = ?, cancellation_reason = ? WHERE id = ?",
            (cancelled_at.isoformat(), reason, booking_id))
        return self.get_booking(booking_id)

    def add_notification(self, user_id, message, created_at):
        self.connection.execute(
            'INSERT INTO notifications(user_id, message, created_at) VALUES (?, ?, ?)',
            (user_id, message, created_at.isoformat()))

    def list_notifications(self, user_id):
        return [Notification(row['id'], row['user_id'], row['message'],
                             datetime.fromisoformat(row['created_at']))
                for row in self.connection.execute(
                    'SELECT * FROM notifications WHERE user_id = ? ORDER BY id', (user_id,))]
    
    @staticmethod
    def _request(row):
        return ExceptionRequest(
            row['id'], row['booking_id'], row['requester_id'], row['reason'],
            RequestStatus(row['status']), datetime.fromisoformat(row['created_at']),
            row['decided_by'],
            datetime.fromisoformat(row['decided_at']) if row['decided_at'] else None,
            row['decision_note'])

    def add_exception_request(self, booking_id, requester_id, reason, created_at):
        """Chamar dentro de `transaction()`: a checagem e o INSERT são atômicos."""
        open_request = self.connection.execute(
            "SELECT 1 FROM exception_requests WHERE booking_id = ? "
            "AND status IN ('PENDING', 'APPROVED')", (booking_id,)).fetchone()
        if open_request:
            raise RequestStateError(
                'Já existe solicitação pendente ou aprovada para esta reserva.')
        cursor = self.connection.execute(
            'INSERT INTO exception_requests(booking_id, requester_id, reason, created_at) '
            'VALUES (?, ?, ?, ?)',
            (booking_id, requester_id, reason, created_at.isoformat()))
        return self.get_exception_request(cursor.lastrowid)

    def get_exception_request(self, request_id):
        row = self.connection.execute('SELECT * FROM exception_requests WHERE id = ?',
                                      (request_id,)).fetchone()
        if row is None:
            raise ValueError('Solicitação inexistente.')
        return self._request(row)

    def list_exception_requests(self, status=None, booking_id=None):
        clauses, params = [], []
        if status is not None:
            clauses.append('status = ?')
            params.append(RequestStatus(status).value)
        if booking_id is not None:
            clauses.append('booking_id = ?')
            params.append(booking_id)
        where = f' WHERE {" AND ".join(clauses)}' if clauses else ''
        rows = self.connection.execute(
            f'SELECT * FROM exception_requests{where} ORDER BY id', params)
        return [self._request(row) for row in rows]

    def decide_exception_request(self, request_id, status, decided_by, decided_at, note):
        """Só decide solicitações PENDING. Chamar dentro de `transaction()`."""
        request = self.get_exception_request(request_id)
        if request.status != RequestStatus.PENDING:
            raise RequestStateError('A solicitação já foi analisada.')
        self.connection.execute(
            'UPDATE exception_requests SET status = ?, decided_by = ?, decided_at = ?, '
            'decision_note = ? WHERE id = ?',
            (RequestStatus(status).value, decided_by, decided_at.isoformat(), note, request_id))
        return self.get_exception_request(request_id)

    @staticmethod
    def _feedback(row):
        return Feedback(row['id'], row['booking_id'], row['student_id'], row['rating'],
                        row['comment'], datetime.fromisoformat(row['created_at']))

    def add_feedback(self, booking_id, student_id, rating, comment, created_at):
        """Chamar dentro de `transaction()`: uma avaliação por reserva."""
        if self.connection.execute('SELECT 1 FROM feedback WHERE booking_id = ?',
                                   (booking_id,)).fetchone():
            raise ValueError('Esta reserva já foi avaliada.')
        cursor = self.connection.execute(
            'INSERT INTO feedback(booking_id, student_id, rating, comment, created_at) '
            'VALUES (?, ?, ?, ?, ?)',
            (booking_id, student_id, rating, comment, created_at.isoformat()))
        return self._feedback(self.connection.execute(
            'SELECT * FROM feedback WHERE id = ?', (cursor.lastrowid,)).fetchone())

    def list_feedback(self):
        return [self._feedback(row) for row in
                self.connection.execute('SELECT * FROM feedback ORDER BY id')]

    @staticmethod
    def _attendance(row):
        return Attendance(row['id'], row['booking_id'], AttendanceStatus(row['status']),
                          row['marked_by'], datetime.fromisoformat(row['marked_at']))

    def add_attendance(self, booking_id, status, marked_by, marked_at):
        """Chamar dentro de `transaction()`: uma marcação por reserva."""
        if self.connection.execute('SELECT 1 FROM attendance WHERE booking_id = ?',
                                   (booking_id,)).fetchone():
            raise ValueError('A presença desta reserva já foi registrada.')
        cursor = self.connection.execute(
            'INSERT INTO attendance(booking_id, status, marked_by, marked_at) VALUES (?, ?, ?, ?)',
            (booking_id, AttendanceStatus(status).value, marked_by, marked_at.isoformat()))
        return self._attendance(self.connection.execute(
            'SELECT * FROM attendance WHERE id = ?', (cursor.lastrowid,)).fetchone())

    def get_attendance(self, booking_id):
        """Marcação da reserva, ou None se ainda não foi registrada."""
        row = self.connection.execute('SELECT * FROM attendance WHERE booking_id = ?',
                                      (booking_id,)).fetchone()
        return self._attendance(row) if row else None

    def list_attendance(self):
        return [self._attendance(row) for row in
                self.connection.execute('SELECT * FROM attendance ORDER BY id')]

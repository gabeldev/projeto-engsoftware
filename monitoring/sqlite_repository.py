"""Persistência SQLite; transações protegem as regras de reserva."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from monitoring.models import AppointmentSlot, Booking, Notification


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

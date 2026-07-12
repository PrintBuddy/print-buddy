import unittest

from sqlmodel import Session, SQLModel, create_engine

from src.core.print_assistant import PrintAssistant
from src.db.crud.user import UserService
from src.db.models.user import User


class MoneyRoundingTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        SQLModel.metadata.create_all(self.engine)

    def test_balance_updates_are_rounded_to_cents(self):
        user_service = UserService()

        with Session(self.engine) as session:
            user = User(
                username="money_user",
                name="Money",
                surname="User",
                pwd="secret",
                email="money@example.com",
                balance=0.10,
                credit_limit=0.00,
            )
            session.add(user)
            session.commit()
            session.refresh(user)

            result = user_service.adjust_balance(str(user.id), -0.04, session)

            self.assertTrue(result.ok)
            self.assertEqual(result.new_balance, 0.06)
            self.assertEqual(user_service.get_user_balance(user.id, session), 0.06)

    def test_debit_within_credit_limit_succeeds_at_boundary(self):
        user_service = UserService()

        with Session(self.engine) as session:
            user = User(
                username="credit_user",
                name="Credit",
                surname="User",
                pwd="secret",
                email="credit@example.com",
                balance=0.10,
                credit_limit=0.00,
            )
            session.add(user)
            session.commit()
            session.refresh(user)

            # Simulate a legacy imprecise float already persisted in the DB.
            user.balance = 0.05999999999999999
            session.add(user)
            session.commit()

            # Debiting exactly down to the (rounded) available balance
            # should succeed rather than being rejected by float drift.
            result = user_service.adjust_balance(str(user.id), -0.06, session)
            self.assertTrue(result.ok)
            self.assertEqual(result.new_balance, 0.0)

    def test_debit_past_credit_limit_is_rejected(self):
        user_service = UserService()

        with Session(self.engine) as session:
            user = User(
                username="limited_user",
                name="Limited",
                surname="User",
                pwd="secret",
                email="limited@example.com",
                balance=0.0,
                credit_limit=0.0,
            )
            session.add(user)
            session.commit()
            session.refresh(user)

            result = user_service.adjust_balance(str(user.id), -0.01, session)
            self.assertFalse(result.ok)
            self.assertEqual(result.reason, "insufficient_funds")
            self.assertEqual(user_service.get_user_balance(user.id, session), 0.0)


if __name__ == "__main__":
    unittest.main()

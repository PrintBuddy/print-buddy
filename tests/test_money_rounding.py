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

            user_service.discount_credit(user.id, 0.04, session)

            session.refresh(user)

            self.assertEqual(user.balance, 0.06)
            self.assertEqual(user_service.get_user_balance(user.id, session), 0.06)

    def test_credit_check_uses_rounded_money_values(self):
        print_assistant = PrintAssistant()

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

            self.assertTrue(print_assistant.check_enough_credit(user.id, 0.06, session))


if __name__ == "__main__":
    unittest.main()

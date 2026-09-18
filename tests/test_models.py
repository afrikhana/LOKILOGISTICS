# -*- coding: utf-8 -*-
"""Model unit tests."""
import datetime as dt

import pytest

from lokiLogistics.merchants.models import Merchant, Merchant, Role, User

from .factories import UserFactory


@pytest.mark.usefixtures("db")
class TestMerchant:
    """Merchant tests."""

    def test_get_by_id(self):
        """Get merchant by ID."""
        merchant = Merchant(business_name="Foo Inc.", email="foo@bar.com", phone="123-456-7890")
        merchant.save()

        retrieved = Merchant.get_by_id(merchant.id)
        assert retrieved == merchant

    def test_created_at_defaults_to_datetime(self):
        """Test creation date."""
        merchant = Merchant(business_name="Foo Inc.", email="foo@bar.com", phone="123-456-7890")
        merchant.save()
        assert bool(merchant.created_at)
        assert isinstance(merchant.created_at, dt.datetime)

    def test_password_is_nullable(self):
        """Test null password."""
        user = User(username="foo", email="foo@bar.com")
        user.save()
        assert user.password is None

    def test_factory(self, db):
        """Test user factory."""
        user = UserFactory(password="myprecious")
        db.session.commit()
        assert bool(user.username)
        assert bool(user.email)
        assert bool(user.created_at)
        assert user.is_admin is False
        assert user.active is True
        assert user.check_password("myprecious")

    def test_check_password(self):
        """Check password."""
        user = User.create(username="foo", email="foo@bar.com", password="foobarbaz123")
        assert user.check_password("foobarbaz123") is True
        assert user.check_password("barfoobaz") is False

    def test_full_name(self):
        """User full name."""
        user = UserFactory(first_name="Foo", last_name="Bar")
        assert user.full_name == "Foo Bar"

    def test_roles(self):
        """Add a role to a user."""
        role = Role(name="admin")
        role.save()
        user = UserFactory()
        user.roles.append(role)
        user.save()
        assert role in user.roles

    def test_roles_repr(self):
        """Check __repr__ output for Role."""
        role = Role(name="user")
        assert role.__repr__() == "<Role(user)>"

    def test_user_repr(self):
        """Check __repr__ output for User."""
        user = User(username="foo", email="foo@bar.com")
        assert user.__repr__() == "<User('foo')>"

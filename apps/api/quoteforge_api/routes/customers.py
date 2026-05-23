"""Customer CRUD (§13). Every query is scoped by user_id (§16, no cross-tenant reads)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from quoteforge_api.auth.dependencies import CurrentUser, SessionDep
from quoteforge_api.models import Customer
from quoteforge_api.schemas.customer import CustomerCreate, CustomerOut, CustomerUpdate

router = APIRouter(prefix="/api/customers", tags=["customers"])


async def _get_owned(session: SessionDep, user: CurrentUser, customer_id: uuid.UUID) -> Customer:
    customer = await session.scalar(
        select(Customer).where(Customer.id == customer_id, Customer.user_id == user.id)
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get("", response_model=list[CustomerOut])
async def list_customers(user: CurrentUser, session: SessionDep) -> list[Customer]:
    rows = await session.scalars(
        select(Customer).where(Customer.user_id == user.id).order_by(Customer.created_at.desc())
    )
    return list(rows)


@router.post("", response_model=CustomerOut, status_code=201)
async def create_customer(
    body: CustomerCreate, user: CurrentUser, session: SessionDep
) -> Customer:
    customer = Customer(user_id=user.id, **body.model_dump())
    session.add(customer)
    await session.commit()
    await session.refresh(customer)
    return customer


@router.get("/{customer_id}", response_model=CustomerOut)
async def get_customer(
    customer_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Customer:
    return await _get_owned(session, user, customer_id)


@router.patch("/{customer_id}", response_model=CustomerOut)
async def update_customer(
    customer_id: uuid.UUID, body: CustomerUpdate, user: CurrentUser, session: SessionDep
) -> Customer:
    customer = await _get_owned(session, user, customer_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    await session.commit()
    await session.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(
    customer_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> None:
    customer = await _get_owned(session, user, customer_id)
    await session.delete(customer)
    await session.commit()

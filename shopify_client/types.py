from enum import StrEnum
from typing import Literal, NotRequired, TypedDict


class ShopifyWebhookTopic(StrEnum):
    APP_PURCHASES_ONE_TIME_UPDATE = "APP_PURCHASES_ONE_TIME_UPDATE"
    APP_SUBSCRIPTIONS_APPROACHING_CAPPED_AMOUNT = "APP_SUBSCRIPTIONS_APPROACHING_CAPPED_AMOUNT"
    APP_SUBSCRIPTIONS_UPDATE = "APP_SUBSCRIPTIONS_UPDATE"
    APP_UNINSTALLED = "APP_UNINSTALLED"
    ATTRIBUTED_SESSIONS_FIRST = "ATTRIBUTED_SESSIONS_FIRST"
    ATTRIBUTED_SESSIONS_LAST = "ATTRIBUTED_SESSIONS_LAST"
    AUDIT_EVENTS_ADMIN_API_ACTIVITY = "AUDIT_EVENTS_ADMIN_API_ACTIVITY"
    BULK_OPERATIONS_FINISH = "BULK_OPERATIONS_FINISH"
    CARTS_CREATE = "CARTS_CREATE"
    CARTS_UPDATE = "CARTS_UPDATE"
    CHANNELS_DELETE = "CHANNELS_DELETE"
    CHECKOUTS_CREATE = "CHECKOUTS_CREATE"
    CHECKOUTS_DELETE = "CHECKOUTS_DELETE"
    CHECKOUTS_UPDATE = "CHECKOUTS_UPDATE"
    COLLECTION_LISTINGS_ADD = "COLLECTION_LISTINGS_ADD"
    COLLECTION_LISTINGS_REMOVE = "COLLECTION_LISTINGS_REMOVE"
    COLLECTION_LISTINGS_UPDATE = "COLLECTION_LISTINGS_UPDATE"
    COLLECTION_PUBLICATIONS_CREATE = "COLLECTION_PUBLICATIONS_CREATE"
    COLLECTION_PUBLICATIONS_DELETE = "COLLECTION_PUBLICATIONS_DELETE"
    COLLECTION_PUBLICATIONS_UPDATE = "COLLECTION_PUBLICATIONS_UPDATE"
    COLLECTIONS_CREATE = "COLLECTIONS_CREATE"
    COLLECTIONS_DELETE = "COLLECTIONS_DELETE"
    COLLECTIONS_UPDATE = "COLLECTIONS_UPDATE"
    CUSTOMER_GROUPS_CREATE = "CUSTOMER_GROUPS_CREATE"
    CUSTOMER_GROUPS_DELETE = "CUSTOMER_GROUPS_DELETE"
    CUSTOMER_GROUPS_UPDATE = "CUSTOMER_GROUPS_UPDATE"
    CUSTOMER_PAYMENT_METHODS_CREATE = "CUSTOMER_PAYMENT_METHODS_CREATE"
    CUSTOMER_PAYMENT_METHODS_REVOKE = "CUSTOMER_PAYMENT_METHODS_REVOKE"
    CUSTOMER_PAYMENT_METHODS_UPDATE = "CUSTOMER_PAYMENT_METHODS_UPDATE"
    CUSTOMERS_CREATE = "CUSTOMERS_CREATE"
    CUSTOMERS_DELETE = "CUSTOMERS_DELETE"
    CUSTOMERS_DISABLE = "CUSTOMERS_DISABLE"
    CUSTOMERS_ENABLE = "CUSTOMERS_ENABLE"
    CUSTOMERS_MARKETING_CONSENT_UPDATE = "CUSTOMERS_MARKETING_CONSENT_UPDATE"
    CUSTOMERS_UPDATE = "CUSTOMERS_UPDATE"
    DISPUTES_CREATE = "DISPUTES_CREATE"
    DISPUTES_UPDATE = "DISPUTES_UPDATE"
    DOMAINS_CREATE = "DOMAINS_CREATE"
    DOMAINS_DESTROY = "DOMAINS_DESTROY"
    DOMAINS_UPDATE = "DOMAINS_UPDATE"
    DRAFT_ORDERS_CREATE = "DRAFT_ORDERS_CREATE"
    DRAFT_ORDERS_DELETE = "DRAFT_ORDERS_DELETE"
    DRAFT_ORDERS_UPDATE = "DRAFT_ORDERS_UPDATE"
    FULFILLMENT_EVENTS_CREATE = "FULFILLMENT_EVENTS_CREATE"
    FULFILLMENT_EVENTS_DELETE = "FULFILLMENT_EVENTS_DELETE"
    FULFILLMENT_ORDERS_CANCELLATION_REQUEST_ACCEPTED = "FULFILLMENT_ORDERS_CANCELLATION_REQUEST_ACCEPTED"
    FULFILLMENT_ORDERS_CANCELLATION_REQUEST_REJECTED = "FULFILLMENT_ORDERS_CANCELLATION_REQUEST_REJECTED"
    FULFILLMENT_ORDERS_CANCELLATION_REQUEST_SUBMITTED = "FULFILLMENT_ORDERS_CANCELLATION_REQUEST_SUBMITTED"
    FULFILLMENT_ORDERS_CANCELLED = "FULFILLMENT_ORDERS_CANCELLED"
    FULFILLMENT_ORDERS_FULFILLMENT_REQUEST_ACCEPTED = "FULFILLMENT_ORDERS_FULFILLMENT_REQUEST_ACCEPTED"
    FULFILLMENT_ORDERS_FULFILLMENT_REQUEST_REJECTED = "FULFILLMENT_ORDERS_FULFILLMENT_REQUEST_REJECTED"
    FULFILLMENT_ORDERS_FULFILLMENT_REQUEST_SUBMITTED = "FULFILLMENT_ORDERS_FULFILLMENT_REQUEST_SUBMITTED"
    FULFILLMENT_ORDERS_FULFILLMENT_SERVICE_FAILED_TO_COMPLETE = (
        "FULFILLMENT_ORDERS_FULFILLMENT_SERVICE_FAILED_TO_COMPLETE"
    )
    FULFILLMENT_ORDERS_HOLD_RELEASED = "FULFILLMENT_ORDERS_HOLD_RELEASED"
    FULFILLMENT_ORDERS_LINE_ITEMS_PREPARED_FOR_LOCAL_DELIVERY = (
        "FULFILLMENT_ORDERS_LINE_ITEMS_PREPARED_FOR_LOCAL_DELIVERY"
    )
    FULFILLMENT_ORDERS_LINE_ITEMS_PREPARED_FOR_PICKUP = "FULFILLMENT_ORDERS_LINE_ITEMS_PREPARED_FOR_PICKUP"
    FULFILLMENT_ORDERS_MOVED = "FULFILLMENT_ORDERS_MOVED"
    FULFILLMENT_ORDERS_ORDER_ROUTING_COMPLETE = "FULFILLMENT_ORDERS_ORDER_ROUTING_COMPLETE"
    FULFILLMENT_ORDERS_PLACED_ON_HOLD = "FULFILLMENT_ORDERS_PLACED_ON_HOLD"
    FULFILLMENT_ORDERS_RESCHEDULED = "FULFILLMENT_ORDERS_RESCHEDULED"
    FULFILLMENT_ORDERS_SCHEDULED_FULFILLMENT_ORDER_READY = "FULFILLMENT_ORDERS_SCHEDULED_FULFILLMENT_ORDER_READY"
    FULFILLMENTS_CREATE = "FULFILLMENTS_CREATE"
    FULFILLMENTS_UPDATE = "FULFILLMENTS_UPDATE"
    INVENTORY_ITEMS_CREATE = "INVENTORY_ITEMS_CREATE"
    INVENTORY_ITEMS_DELETE = "INVENTORY_ITEMS_DELETE"
    INVENTORY_ITEMS_UPDATE = "INVENTORY_ITEMS_UPDATE"
    INVENTORY_LEVELS_CONNECT = "INVENTORY_LEVELS_CONNECT"
    INVENTORY_LEVELS_DISCONNECT = "INVENTORY_LEVELS_DISCONNECT"
    INVENTORY_LEVELS_UPDATE = "INVENTORY_LEVELS_UPDATE"
    LOCALES_CREATE = "LOCALES_CREATE"
    LOCALES_UPDATE = "LOCALES_UPDATE"
    LOCATIONS_ACTIVATE = "LOCATIONS_ACTIVATE"
    LOCATIONS_CREATE = "LOCATIONS_CREATE"
    LOCATIONS_DEACTIVATE = "LOCATIONS_DEACTIVATE"
    LOCATIONS_DELETE = "LOCATIONS_DELETE"
    LOCATIONS_UPDATE = "LOCATIONS_UPDATE"
    MARKETS_CREATE = "MARKETS_CREATE"
    MARKETS_DELETE = "MARKETS_DELETE"
    MARKETS_UPDATE = "MARKETS_UPDATE"
    ORDER_TRANSACTIONS_CREATE = "ORDER_TRANSACTIONS_CREATE"
    ORDERS_CANCELLED = "ORDERS_CANCELLED"
    ORDERS_CREATE = "ORDERS_CREATE"
    ORDERS_DELETE = "ORDERS_DELETE"
    ORDERS_EDITED = "ORDERS_EDITED"
    ORDERS_FULFILLED = "ORDERS_FULFILLED"
    ORDERS_PAID = "ORDERS_PAID"
    ORDERS_PARTIALLY_FULFILLED = "ORDERS_PARTIALLY_FULFILLED"
    ORDERS_UPDATED = "ORDERS_UPDATED"
    PAYMENT_SCHEDULES_DUE = "PAYMENT_SCHEDULES_DUE"
    PAYMENT_TERMS_CREATE = "PAYMENT_TERMS_CREATE"
    PAYMENT_TERMS_DELETE = "PAYMENT_TERMS_DELETE"
    PAYMENT_TERMS_UPDATE = "PAYMENT_TERMS_UPDATE"
    PRODUCT_LISTINGS_ADD = "PRODUCT_LISTINGS_ADD"
    PRODUCT_LISTINGS_REMOVE = "PRODUCT_LISTINGS_REMOVE"
    PRODUCT_LISTINGS_UPDATE = "PRODUCT_LISTINGS_UPDATE"
    PRODUCT_PUBLICATIONS_CREATE = "PRODUCT_PUBLICATIONS_CREATE"
    PRODUCT_PUBLICATIONS_DELETE = "PRODUCT_PUBLICATIONS_DELETE"
    PRODUCT_PUBLICATIONS_UPDATE = "PRODUCT_PUBLICATIONS_UPDATE"
    PRODUCTS_CREATE = "PRODUCTS_CREATE"
    PRODUCTS_DELETE = "PRODUCTS_DELETE"
    PRODUCTS_UPDATE = "PRODUCTS_UPDATE"
    PROFILES_CREATE = "PROFILES_CREATE"
    PROFILES_DELETE = "PROFILES_DELETE"
    PROFILES_UPDATE = "PROFILES_UPDATE"
    REFUNDS_CREATE = "REFUNDS_CREATE"
    RETURNS_APPROVE = "RETURNS_APPROVE"
    RETURNS_CANCEL = "RETURNS_CANCEL"
    RETURNS_CLOSE = "RETURNS_CLOSE"
    RETURNS_DECLINE = "RETURNS_DECLINE"
    RETURNS_REOPEN = "RETURNS_REOPEN"
    RETURNS_REQUEST = "RETURNS_REQUEST"
    REVERSE_DELIVERIES_ATTACH_DELIVERABLE = "REVERSE_DELIVERIES_ATTACH_DELIVERABLE"
    REVERSE_FULFILLMENT_ORDERS_DISPOSE = "REVERSE_FULFILLMENT_ORDERS_DISPOSE"
    SCHEDULED_PRODUCT_LISTINGS_ADD = "SCHEDULED_PRODUCT_LISTINGS_ADD"
    SCHEDULED_PRODUCT_LISTINGS_REMOVE = "SCHEDULED_PRODUCT_LISTINGS_REMOVE"
    SCHEDULED_PRODUCT_LISTINGS_UPDATE = "SCHEDULED_PRODUCT_LISTINGS_UPDATE"
    SEGMENTS_CREATE = "SEGMENTS_CREATE"
    SEGMENTS_DELETE = "SEGMENTS_DELETE"
    SEGMENTS_UPDATE = "SEGMENTS_UPDATE"
    SELLING_PLAN_GROUPS_CREATE = "SELLING_PLAN_GROUPS_CREATE"
    SELLING_PLAN_GROUPS_DELETE = "SELLING_PLAN_GROUPS_DELETE"
    SELLING_PLAN_GROUPS_UPDATE = "SELLING_PLAN_GROUPS_UPDATE"
    SHIPPING_ADDRESSES_CREATE = "SHIPPING_ADDRESSES_CREATE"
    SHIPPING_ADDRESSES_UPDATE = "SHIPPING_ADDRESSES_UPDATE"
    SHOP_UPDATE = "SHOP_UPDATE"
    SUBSCRIPTION_BILLING_ATTEMPTS_CHALLENGED = "SUBSCRIPTION_BILLING_ATTEMPTS_CHALLENGED"
    SUBSCRIPTION_BILLING_ATTEMPTS_FAILURE = "SUBSCRIPTION_BILLING_ATTEMPTS_FAILURE"
    SUBSCRIPTION_BILLING_ATTEMPTS_SUCCESS = "SUBSCRIPTION_BILLING_ATTEMPTS_SUCCESS"
    SUBSCRIPTION_BILLING_CYCLE_EDITS_CREATE = "SUBSCRIPTION_BILLING_CYCLE_EDITS_CREATE"
    SUBSCRIPTION_BILLING_CYCLE_EDITS_DELETE = "SUBSCRIPTION_BILLING_CYCLE_EDITS_DELETE"
    SUBSCRIPTION_BILLING_CYCLE_EDITS_UPDATE = "SUBSCRIPTION_BILLING_CYCLE_EDITS_UPDATE"
    SUBSCRIPTION_CONTRACTS_CREATE = "SUBSCRIPTION_CONTRACTS_CREATE"
    SUBSCRIPTION_CONTRACTS_UPDATE = "SUBSCRIPTION_CONTRACTS_UPDATE"
    TAX_SERVICES_CREATE = "TAX_SERVICES_CREATE"
    TAX_SERVICES_UPDATE = "TAX_SERVICES_UPDATE"
    TENDER_TRANSACTIONS_CREATE = "TENDER_TRANSACTIONS_CREATE"
    THEMES_CREATE = "THEMES_CREATE"
    THEMES_DELETE = "THEMES_DELETE"
    THEMES_PUBLISH = "THEMES_PUBLISH"
    THEMES_UPDATE = "THEMES_UPDATE"
    VARIANTS_IN_STOCK = "VARIANTS_IN_STOCK"
    VARIANTS_OUT_OF_STOCK = "VARIANTS_OUT_OF_STOCK"


class WebhookSubscriptionInput(TypedDict):
    arn: str
    format: Literal["JSON"]
    filter: NotRequired[str]
    includeFields: NotRequired[list[str]]

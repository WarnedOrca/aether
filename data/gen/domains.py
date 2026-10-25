"""Business domains for synthetic data. Each domain names its sheets and the role of each column.

These are invented, generic small-business setups, not real clients.
Roles let one procedure pattern work across many domains.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Entity:
    sheet: str  # alias == title (generator keeps them equal)
    noun: str  # "patient", "student", ...
    person: str  # column holding the person's name
    contact: str  # phone or email column
    channel: str  # sms | email
    when: str  # main Date/DateTime column (appointment, due date, last visit...)
    when_type: str  # Date | DateTime
    when_noun: str  # "appointment", "due date", ...
    status: str
    money: str | None = None  # Money column, if any
    money_noun: str = "amount"
    private: str | None = None  # private Text column (never in messages)
    private_noun: str = "notes"


@dataclass(frozen=True)
class Stock:
    sheet: str
    item: str
    qty: str
    minimum: str
    reorder: str
    supplier: str
    unit_cost: str
    noun: str  # "supplies", "ingredients"


@dataclass(frozen=True)
class Domain:
    name: str
    business: str  # "dental office"
    owner_word: str  # how the owner refers to the business
    entity: Entity
    stock: Stock | None = None
    calendar: str | None = None
    statuses: tuple[str, ...] = ("booked", "done", "no-show", "cancelled")
    extra: dict = field(default_factory=dict)


def _e(sheet, noun, person, contact, channel, when, when_type, when_noun, status="status", money=None,
       money_noun="amount", private=None, private_noun="notes"):
    return Entity(sheet, noun, person, contact, channel, when, when_type, when_noun, status, money, money_noun,
                  private, private_noun)


DOMAINS: list[Domain] = [
    Domain("clinic", "family clinic", "the clinic",
           _e("Visits", "patient", "patient", "phone", "sms", "starts", "DateTime", "appointment",
              money="copay", money_noun="copay", private="diagnosis", private_noun="diagnosis"),
           calendar="Rooms"),
    Domain("dental", "dental office", "the office",
           _e("Patients", "patient", "name", "mobile", "sms", "next_visit", "DateTime", "cleaning",
              money="balance", money_noun="balance", private="medical_history", private_noun="medical history"),
           calendar="Chairs"),
    Domain("tutoring", "tutoring center", "the center",
           _e("Students", "student", "student", "parent_email", "email", "next_session", "DateTime", "session",
              money="balance", money_noun="balance", private="learning_notes", private_noun="learning notes"),
           statuses=("scheduled", "done", "missed", "cancelled")),
    Domain("restaurant", "restaurant", "the restaurant",
           _e("Bookings", "guest", "guest", "phone", "sms", "at", "DateTime", "reservation",
              money="deposit", money_noun="deposit", private="allergies", private_noun="allergy notes"),
           stock=Stock("Pantry", "item", "on_hand", "minimum", "reorder_qty", "supplier", "unit_cost", "ingredients"),
           calendar="Tables", statuses=("booked", "seated", "no-show", "cancelled")),
    Domain("retail", "gift shop", "the shop",
           _e("Orders", "customer", "customer", "email", "email", "ordered_on", "Date", "order",
              money="total", money_noun="order total", private="card_note", private_noun="payment notes"),
           stock=Stock("Stock", "product", "qty", "min_qty", "reorder_qty", "vendor", "cost", "products"),
           statuses=("new", "shipped", "returned", "cancelled")),
    Domain("salon", "hair salon", "the salon",
           _e("Clients", "client", "name", "phone", "sms", "last_visit", "Date", "last visit",
              money="tab", money_noun="tab", private="color_formula", private_noun="color formula"),
           calendar="Stylists", statuses=("active", "lapsed", "booked", "cancelled")),
    Domain("gym", "gym", "the gym",
           _e("Members", "member", "name", "email", "email", "renews_on", "Date", "renewal date",
              money="dues", money_noun="dues", private="health_notes", private_noun="health notes"),
           statuses=("active", "expired", "frozen", "cancelled")),
    Domain("autorepair", "auto repair shop", "the shop",
           _e("Jobs", "customer", "owner_name", "phone", "sms", "promised", "DateTime", "pickup time",
              money="estimate", money_noun="estimate", private="vin", private_noun="VIN"),
           stock=Stock("Parts", "part", "count", "minimum", "reorder_qty", "supplier", "unit_price", "parts"),
           calendar="Bays", statuses=("open", "ready", "picked-up", "cancelled")),
    Domain("bakery", "bakery", "the bakery",
           _e("CakeOrders", "customer", "customer", "email", "email", "pickup", "Date", "pickup date",
              money="price", money_noun="price", private="address", private_noun="home address"),
           stock=Stock("Ingredients", "ingredient", "on_hand", "minimum", "reorder_qty", "supplier", "unit_cost",
                       "ingredients"),
           calendar="Ovens", statuses=("new", "confirmed", "ready", "cancelled")),
    Domain("landscaping", "landscaping company", "the company",
           _e("Quotes", "customer", "customer", "email", "email", "sent_on", "Date", "quote",
              money="amount", money_noun="quote amount", private="gate_code", private_noun="gate code"),
           statuses=("draft", "sent", "accepted", "declined")),
    Domain("daycare", "daycare", "the daycare",
           _e("Families", "family", "parent", "email", "email", "due_date", "Date", "tuition due date",
              money="balance", money_noun="balance", private="health_notes", private_noun="health notes"),
           statuses=("enrolled", "waitlist", "withdrawn", "paused")),
    Domain("vet", "veterinary clinic", "the clinic",
           _e("Pets", "pet owner", "owner", "phone", "sms", "vaccine_due", "Date", "vaccination",
              money="balance", money_noun="balance", private="medical_notes", private_noun="medical notes"),
           calendar="ExamRooms", statuses=("active", "due", "overdue", "inactive")),
    Domain("cleaning", "cleaning service", "the service",
           _e("Cleanings", "client", "client", "phone", "sms", "scheduled", "DateTime", "cleaning",
              money="fee", money_noun="fee", private="door_code", private_noun="door code"),
           stock=Stock("Supplies", "supply", "qty", "minimum", "reorder_qty", "supplier", "cost", "supplies"),
           statuses=("booked", "done", "skipped", "cancelled")),
    Domain("music", "music school", "the school",
           _e("Lessons", "student", "student", "parent_phone", "sms", "lesson_at", "DateTime", "lesson",
              money="balance", money_noun="balance", private="progress_notes", private_noun="progress notes"),
           calendar="Studios", statuses=("scheduled", "done", "missed", "cancelled")),
    Domain("bikeshop", "bike shop", "the shop",
           _e("Repairs", "customer", "customer", "phone", "sms", "ready_on", "Date", "repair",
              money="estimate", money_noun="estimate", private="lock_code", private_noun="lock code"),
           stock=Stock("Parts", "part", "qty", "minimum", "reorder_qty", "supplier", "unit_cost", "parts"),
           statuses=("waiting", "ready", "picked-up", "cancelled")),
    Domain("florist", "flower shop", "the shop",
           _e("Deliveries", "customer", "customer", "email", "email", "deliver_on", "Date", "delivery",
              money="price", money_noun="price", private="card_message", private_noun="card message"),
           stock=Stock("Flowers", "flower", "stems", "minimum", "reorder_qty", "grower", "unit_cost", "flowers"),
           statuses=("ordered", "delivered", "failed", "cancelled")),
    Domain("plumbing", "plumbing company", "the company",
           _e("Calls", "customer", "customer", "phone", "sms", "visit_at", "DateTime", "service call",
              money="invoice", money_noun="invoice", private="alarm_code", private_noun="alarm code"),
           calendar="Vans", statuses=("booked", "done", "no-access", "cancelled")),
    Domain("bookstore", "bookstore", "the store",
           _e("Holds", "customer", "customer", "email", "email", "held_until", "Date", "hold",
              money="prepaid", money_noun="prepaid amount", private="phone_note", private_noun="private notes"),
           stock=Stock("Inventory", "title", "copies", "minimum", "reorder_qty", "distributor", "unit_cost", "books"),
           statuses=("waiting", "ready", "collected", "expired")),
    Domain("yoga", "yoga studio", "the studio",
           _e("Passes", "student", "name", "email", "email", "expires_on", "Date", "class pass",
              money="credit", money_noun="credit", private="injury_notes", private_noun="injury notes"),
           calendar="Rooms", statuses=("active", "expired", "paused", "cancelled")),
    Domain("petgroomer", "pet grooming salon", "the salon",
           _e("Grooms", "pet owner", "owner", "phone", "sms", "appointment", "DateTime", "grooming",
              money="price", money_noun="price", private="behavior_notes", private_noun="behavior notes"),
           calendar="Tables", statuses=("booked", "done", "no-show", "cancelled")),
    Domain("printshop", "print shop", "the shop",
           _e("Jobs", "customer", "customer", "email", "email", "due", "Date", "print job",
              money="quote", money_noun="quote", private="file_link", private_noun="file link"),
           stock=Stock("Paper", "stock_name", "reams", "minimum", "reorder_qty", "supplier", "unit_cost", "paper"),
           statuses=("queued", "printed", "collected", "cancelled")),
    Domain("photostudio", "photography studio", "the studio",
           _e("Shoots", "client", "client", "email", "email", "shoot_on", "Date", "photo shoot",
              money="deposit", money_noun="deposit", private="venue_notes", private_noun="venue notes"),
           calendar="Studio", statuses=("booked", "shot", "delivered", "cancelled")),
]

# Held out entirely from training: used only for the synthetic test split.
TEST_DOMAINS = {"vet", "florist", "photostudio", "plumbing"}

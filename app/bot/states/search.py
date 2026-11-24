from aiogram.fsm.state import State, StatesGroup


class SearchState(StatesGroup):
    waiting_origin = State()
    waiting_origin_manual = State()
    waiting_origin_choice = State()

    waiting_destination = State()
    waiting_destination_manual = State()
    waiting_destination_choice = State()

    waiting_date_type = State()
    waiting_departure_date = State()
    waiting_departure_range = State()

    waiting_round_trip = State()
    waiting_return_date = State()
    waiting_return_range = State()

    waiting_filters = State()
    waiting_max_price = State()

    viewing_results = State()


class SettingsState(StatesGroup):
    waiting_language = State()
    waiting_currency = State()


class EditSubscriptionState(StatesGroup):
    waiting_new_max_price = State()

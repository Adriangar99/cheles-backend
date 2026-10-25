"""Reading stored strings back into the domain's Literal types, checking them instead of casting."""


def parse_literal[T: str](value: str, allowed: tuple[T, ...]) -> T:
    """`value` as one of `allowed` (a Literal's values, e.g. `get_args(Kind)`); raises ValueError otherwise."""
    for option in allowed:
        if option == value:
            return option
    raise ValueError(f"{value!r} is not one of {allowed}")

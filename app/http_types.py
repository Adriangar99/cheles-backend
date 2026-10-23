"""Pydantic field types for HTTP response models that keep the JSON the API has always returned.

Pydantic's defaults would encode Decimal as a string and UTC datetimes with a `Z`; these types keep FastAPI's
historical encoding (numbers, `isoformat()`) while documenting the right schema in the OpenAPI contract.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer, WithJsonSchema


def encode_decimal(value: Decimal) -> int | float:
    """Same rule as `fastapi.encoders.decimal_encoder`: integers stay integers, the rest become floats."""
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and exponent >= 0:
        return int(value)
    return float(value)


JsonDecimal = Annotated[
    Decimal,
    PlainSerializer(encode_decimal, return_type=float),
    WithJsonSchema({"type": "number"}),
]

JsonDateTime = Annotated[
    datetime,
    PlainSerializer(datetime.isoformat, return_type=str),
    WithJsonSchema({"type": "string", "format": "date-time"}),
]

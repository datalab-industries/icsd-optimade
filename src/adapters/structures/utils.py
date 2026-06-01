
from typing import Union
from numbers import Real

from uncertainties import ufloat
from pydantic import BaseModel

class UncertainFloat(BaseModel):
    value: float
    uncertainty: float

    def __init__(
            self, 
            value: float | str, 
            uncertainty: float = 0.0
        ) -> None:

        if isinstance(value, str):
            value, uncertainty = self._cast_real_str_to_uncertain_float(value)

        super().__init__(value=value, uncertainty=uncertainty)

    def _cast_real_str_to_uncertain_float(self, value: str) -> (float, float):
        if "(" in value:
            base, uncertainty = value.split("(")
            uncertainty = uncertainty.rstrip(")")
            scale = 10 ** (-len(base.split(".")[1]))

            return float(base), float(uncertainty) * scale

        return float(value), 0.0

    def _cast_real_to_uncertain_float(self, other: Union[Real, 'UncertainFloat']) -> 'UncertainFloat':
        if isinstance(other, Real):
            other = UncertainFloat(other)
        return other
    
    def __float__(self):
        return self.value

    def __int__(self):
        return int(self.value)

    def __round__(self, n: int = 0):
        return round(self.value, n)

    def __abs__(self):
        return abs(self.value)

    def __neg__(self):
        return -self.value

    def __pos__(self):
        return self.value 

    def __invert__(self):
        return 1 / self.value

    def __str__(self):
        return f"{self.value:.3E} ± {self.uncertainty:.3E}"

    def __repr__(self):
        return f"UncertainFloat(value={self.value:.3E}, uncertainty={self.uncertainty:.3E})"

    def __add__(self, other: Union[Real, 'UncertainFloat']):
        other = self._cast_real_to_uncertain_float(other)
        x = ufloat(self.value, self.uncertainty) + ufloat(other.value, other.uncertainty) 
        return UncertainFloat(x.nominal_value, x.std_dev)

    def __radd__(self, other: Union[Real, 'UncertainFloat']):
        other = self._cast_real_to_uncertain_float(other)
        x = ufloat(other.value, other.uncertainty) + ufloat(self.value, self.uncertainty) 
        return UncertainFloat(x.nominal_value, x.std_dev)

    def __sub__(self, other: Union[Real, 'UncertainFloat']):
        other = self._cast_real_to_uncertain_float(other)
        x = ufloat(self.value, self.uncertainty) - ufloat(other.value, other.uncertainty) 
        return UncertainFloat(x.nominal_value, x.std_dev)

    def __rsub__(self, other: Union[Real, 'UncertainFloat']):
        other = self._cast_real_to_uncertain_float(other)
        x = ufloat(other.value, other.uncertainty) - ufloat(self.value, self.uncertainty) 
        return UncertainFloat(x.nominal_value, x.std_dev)

    def __pow__(self, other: Union[Real, 'UncertainFloat']):
        other = self._cast_real_to_uncertain_float(other)
        x = ufloat(self.value, self.uncertainty) ** ufloat(other.value, other.uncertainty) 
        return UncertainFloat(x.nominal_value, x.std_dev)

    def __rpow__(self, other: Union[Real, 'UncertainFloat']):
        other = self._cast_real_to_uncertain_float(other)
        x = ufloat(other.value, other.uncertainty) ** ufloat(self.value, self.uncertainty) 
        return UncertainFloat(x.nominal_value, x.std_dev)

    def __mod__(self, other: Union[Real, 'UncertainFloat']):
        other = self._cast_real_to_uncertain_float(other)
        x = ufloat(self.value, self.uncertainty) % ufloat(other.value, other.uncertainty) 
        return UncertainFloat(x.nominal_value, x.std_dev)

    def __mul__(self, other: Union[Real, 'UncertainFloat']):
        other = self._cast_real_to_uncertain_float(other)
        x = ufloat(self.value, self.uncertainty) * ufloat(other.value, other.uncertainty) 
        return UncertainFloat(x.nominal_value, x.std_dev)

    def __rmul__(self, other: Union[Real, 'UncertainFloat']):
        other = self._cast_real_to_uncertain_float(other)
        x = ufloat(other.value, other.uncertainty) * ufloat(self.value, self.uncertainty) 
        return UncertainFloat(x.nominal_value, x.std_dev)

    def __truediv__(self, other: Union[Real, 'UncertainFloat']):
        other = self._cast_real_to_uncertain_float(other)
        x = ufloat(self.value, self.uncertainty) / ufloat(other.value, other.uncertainty) 
        return UncertainFloat(x.nominal_value, x.std_dev)

    def __rtruediv__(self, other: Union[Real, 'UncertainFloat']):
        other = self._cast_real_to_uncertain_float(other)
        x = ufloat(other.value, other.uncertainty) / ufloat(self.value, self.uncertainty) 
        return UncertainFloat(x.nominal_value, x.std_dev)

    def __lt__(self, other: Union[Real, 'UncertainFloat']):
        other = self._cast_real_to_uncertain_float(other)
        return ufloat(self.value, self.uncertainty) < ufloat(other.value, other.uncertainty) 

    def __gt__(self, other: Union[Real, 'UncertainFloat']):
        other = self._cast_real_to_uncertain_float(other)
        return ufloat(self.value, self.uncertainty) > ufloat(other.value, other.uncertainty) 

    def __le__(self, other: Union[Real, 'UncertainFloat']):
        other = self._cast_real_to_uncertain_float(other)
        return ufloat(self.value, self.uncertainty) <= ufloat(other.value, other.uncertainty) 

    def __ge__(self, other: Union[Real, 'UncertainFloat']):
        other = self._cast_real_to_uncertain_float(other)
        return ufloat(self.value, self.uncertainty) >= ufloat(other.value, other.uncertainty) 
        
    def __eq__(self, other: Union[Real, 'UncertainFloat']):
        if isinstance(other, Real):
            return self.value == other
        return ufloat(self.value, self.uncertainty) == ufloat(other.value, other.uncertainty) 

    def __ne__(self, other: Union[Real, 'UncertainFloat']):
        if isinstance(other, Real):
            return self.value != other
        return ufloat(self.value, self.uncertainty) != ufloat(other.value, other.uncertainty)  

"""
MINI4WD AI SYSTEM
Vehicle weight estimator

公称トルクと車両条件から、トルク換算の駆動力を
「等価重量」として算出する。

注意:
    これは実走可能重量の保証値ではない。
    3Vベンチマークの実測値や実走データによる補正は
    別レイヤーで行う。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VehicleAssumptions:
    tire_diameter_mm: float = 24.0
    gear_ratio: float = 3.5
    drivetrain_efficiency: float = 0.85

    @property
    def tire_radius_cm(self) -> float:
        return self.tire_diameter_mm / 20.0


@dataclass(frozen=True)
class TorqueWeightEstimate:
    motor_torque_gcm: float
    wheel_torque_gcm: float
    torque_equivalent_weight_g: float


def estimate_torque_equivalent_weight(
    motor_torque_gcm: float,
    assumptions: VehicleAssumptions | None = None,
) -> TorqueWeightEstimate:
    """
    Calculate torque-equivalent load weight.

    g·cm is treated as gram-force-centimeter.
    The returned weight is the tangential-force equivalent at the tire.
    """

    if motor_torque_gcm < 0:
        raise ValueError("motor_torque_gcm must be >= 0")

    a = assumptions or VehicleAssumptions()

    if a.gear_ratio <= 0:
        raise ValueError("gear_ratio must be > 0")
    if not 0 < a.drivetrain_efficiency <= 1:
        raise ValueError("drivetrain_efficiency must be in (0, 1]")

    wheel_torque = (
        motor_torque_gcm
        * a.gear_ratio
        * a.drivetrain_efficiency
    )

    equivalent_weight = wheel_torque / a.tire_radius_cm

    return TorqueWeightEstimate(
        motor_torque_gcm=motor_torque_gcm,
        wheel_torque_gcm=wheel_torque,
        torque_equivalent_weight_g=equivalent_weight,
    )

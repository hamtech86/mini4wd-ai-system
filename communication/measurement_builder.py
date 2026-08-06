"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3

 communication/measurement_builder.py

 CSV dict -> Measurement
=====================================================
"""

from measurement.measurement import Measurement


class MeasurementBuilder:
    """
    CSVParser結果をMeasurementへ変換
    """

    def build(
        self,
        data: dict
    ) -> Measurement:

        return Measurement(

            record_type=data.get(
                "record_type",
                "DATA"
            ),

            device_model=data.get(
                "device_model",
                "UNKNOWN"
            ),

            instance_id=data.get(
                "instance_id",
                "UNKNOWN"
            ),

            elapsed_time=int(
                data.get(
                    "elapsed_time",
                    0
                )
            ),


            raw_acs1=int(
                data.get(
                    "raw_acs1",
                    0
                )
            ),

            raw_acs2=int(
                data.get(
                    "raw_acs2",
                    0
                )
            ),


            current1=float(
                data.get(
                    "current1",
                    0
                )
            ),

            current2=float(
                data.get(
                    "current2",
                    0
                )
            ),


            voltage1=float(
                data.get(
                    "voltage1",
                    0
                )
            ),

            voltage2=float(
                data.get(
                    "voltage2",
                    0
                )
            ),

            motor_voltage=float(
                data.get(
                    "motor_voltage",
                    0
                )
            ),


            pwm=int(
                data.get(
                    "pwm",
                    0
                )
            ),

            direction=data.get(
                "direction",
                "FWD"
            ),

            state=data.get(
                "state",
                "READY"
            ),


            current_avg=float(
                data.get(
                    "current_avg",
                    0
                )
            ),

            power=float(
                data.get(
                    "power",
                    0
                )
            ),

            current_ripple=float(
                data.get(
                    "current_ripple",
                    0
                )
            ),

            voltage_ripple=float(
                data.get(
                    "voltage_ripple",
                    0
                )
            ),


            peak_power=float(
                data.get(
                    "peak_power",
                    0
                )
            ),

            peak_current=float(
                data.get(
                    "peak_current",
                    0
                )
            ),

            peak_voltage=float(
                data.get(
                    "peak_voltage",
                    0
                )
            ),

            peak_pwm=int(
                data.get(
                    "peak_pwm",
                    0
                )
            ),


            brush_peak_current=float(
                data.get(
                    "brush_peak_current",
                    0
                )
            ),


            raw_magnetic=int(
                data.get(
                    "raw_magnetic",
                    0
                )
            ),

            magnetic_level=float(
                data.get(
                    "magnetic_level",
                    0
                )
            ),


            motor_temperature=float(
                data.get(
                    "motor_temperature",
                    0
                )
            ),


            session_id=data.get(
                "session_id"
            )
        )


"""
Real CSV -> Analysis Test
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(ROOT)
)


from communication.csv_parser import CSVParser
from communication.measurement_builder import MeasurementBuilder

from analysis.analysis_engine import AnalysisEngine



def main():

    print("===============================")
    print(" Real Log Analysis Test")
    print("===============================")


    csv_path = ROOT / "logs" / "test_motor.csv"


    if not csv_path.exists():

        print(
            "CSV not found:",
            csv_path
        )

        return


    parser = CSVParser()

    builder = MeasurementBuilder()


    measurement = None


    with open(
        csv_path,
        "r",
        encoding="utf-8"
    ) as f:


        for line in f:

            data = parser.parse(
                line.strip()
            )


            if parser.is_data_record(data):

                measurement = builder.build(
                    data
                )

                break


    if measurement is None:

        print(
            "No DATA record found"
        )

        return



    engine = AnalysisEngine()


    result = engine.analyze(
        measurement
    )


    print()

    print("--- Performance ---")

    print(
        result.performance.estimated_rpm.value
    )

    print(
        result.performance.estimated_torque.value
    )


    print()

    print("--- Strategy ---")

    print(
        result.strategy.recipe_name
    )


    print()

    print("--- Score ---")

    print(
        result.score.total_score,
        result.score.rank
    )


    print()

    print(
        "Real Analysis Complete"
    )



if __name__ == "__main__":

    main()


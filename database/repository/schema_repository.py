# ============================================================
# schema_repository.py
# Motor Database System
# Revision 1
# Schema Information Repository
# ============================================================

from .base_repository import BaseRepository



class SchemaRepository(BaseRepository):


    TABLE = "schema_info"



    def get_info(
        self
    ):

        return self.fetch_one(
            """
            SELECT *

            FROM schema_info

            LIMIT 1

            """
        )



    def get_version(
        self
    ):

        result = self.fetch_one(
            """
            SELECT schema_version

            FROM schema_info

            LIMIT 1

            """
        )


        if result:

            return result["schema_version"]


        return None



    def update_version(
        self,
        version,
        description=None
    ):

        return self.update(
            self.TABLE,
            {
                "schema_version": version,

                "description": description
            },
            "1=1",
            ()
        )



    def update_description(
        self,
        description
    ):

        return self.update(
            self.TABLE,
            {
                "description": description
            },
            "1=1",
            ()
        )



# ============================================================
# END OF schema_repository.py
# ============================================================


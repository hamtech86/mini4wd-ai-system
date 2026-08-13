# ============================================================
# base_repository.py
# Motor Database System
# Revision 1
# Base Repository
# ============================================================


class BaseRepository:


    def __init__(self, database):
        self.database = database


    def execute(self, query, parameters=None):
        if parameters is None:
            parameters = ()
        return self.database.execute(query, parameters)


    def fetch_one(self, query, parameters=None):
        cursor = self.execute(query, parameters)
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


    def fetch_all(self, query, parameters=None):
        cursor = self.execute(query, parameters)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


    def insert(self, table, data):
        columns = ",".join(data.keys())
        placeholders = ",".join(["?" for _ in data])
        query = f"""
        INSERT INTO {table}
        ({columns})
        VALUES
        ({placeholders})
        """
        cursor = self.execute(query, tuple(data.values()))
        self.database.commit()
        return cursor.lastrowid


    def update(self, table, data, where, where_parameters):
        sets = ",".join([f"{key}=?" for key in data.keys()])
        query = f"""
        UPDATE {table}
        SET
            {sets},
            updated_at=CURRENT_TIMESTAMP
        WHERE
            {where}
        """
        parameters = list(data.values()) + list(where_parameters)
        cursor = self.execute(query, parameters)
        self.database.commit()
        return cursor.rowcount


    def soft_delete(self, table, key_name, key_value):
        query = f"""
        UPDATE {table}
        SET
            is_deleted=1,
            updated_at=CURRENT_TIMESTAMP
        WHERE
            {key_name}=?
        """
        cursor = self.execute(query, (key_value,))
        self.database.commit()
        return cursor.rowcount


    def exists(self, table, key_name, key_value):
        query = f"""
        SELECT 1
        FROM {table}
        WHERE
            {key_name}=?
        LIMIT 1
        """
        result = self.fetch_one(query, (key_value,))
        return result is not None


# ============================================================
# END OF base_repository.py
# ============================================================

# ============================================================
# transaction.py
# Motor Database System
# Revision 1
# Transaction Management
# ============================================================

from contextlib import contextmanager


class TransactionManager:


    def __init__(
        self,
        database
    ):

        self.database = database



    def begin(self):

        self.database.begin_transaction()



    def commit(self):

        self.database.commit()



    def rollback(self):

        self.database.rollback()



    @contextmanager
    def transaction(self):

        try:

            self.begin()

            yield


            self.commit()


        except Exception:

            self.rollback()

            raise



    # ========================================================
    # Motor workflow transaction
    #
    # start_work()
    #      |
    # start_session()
    #      |
    # insert_log()
    #      |
    # finish_session()
    #      |
    # finish_work()
    #      |
    # cache_update()
    #
    # ========================================================



    def start_workflow(self):

        self.begin()



    def finish_workflow(self):

        self.commit()



    def cancel_workflow(self):

        self.rollback()



# ============================================================
# END OF transaction.py
# ============================================================


from db.table_info import TABLE_INFO
import psycopg2
import json
from psycopg2.extras import RealDictCursor
from pypika import Table, Query


class Database:
    def __init__(self, secret_config):
        self.user = secret_config['db_user']
        self.port = secret_config['db_port']
        self.dbname = secret_config['db_name']
        self.host = secret_config['db_host']
        self.password = secret_config['db_password']
        self.connection = None

    def __del__(self):
        return self.connection.close()

    def connect(self):
        pg_conn = psycopg2.connect(
            user=self.user,
            port=self.port,
            dbname=self.dbname,
            host=self.host,
            password=self.password
        )
        self.connection = pg_conn

    def get_json_cursor(self):
        return self.connection.cursor(cursor_factory=RealDictCursor)

    @staticmethod
    def execute_and_fetch(cursor, query):
        cursor.execute(query)
        res = cursor.fetchall()
        cursor.close()
        return res

    def read_data(self, query):
        query = str(query)
        cursor = self.get_json_cursor()
        response = self.execute_and_fetch(cursor, query)
        return json.dumps(response, default=str)

    def insert_data(self, query):
        query = str(query)
        self.connection.cursor().execute(query)
        self.connection.commit()
        return

    def get_insert_json_query(self, table_name, json_obj):
        table_info = TABLE_INFO[table_name]
        table_columns = table_info['columns']

        insert_column_list = []
        insert_value_list = []

        for key, value in json_obj.items():
            if key in table_columns:
                insert_column_list.append(key)
                insert_value_list.append(value)

        insert_column = tuple(insert_column_list)
        insert_values = tuple(insert_value_list)

        query = Query.into(Table(table_name)).columns(
            insert_column).insert(insert_values)

        return query

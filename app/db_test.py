import psycopg


def main() -> None:
    print("Connecting with psycopg3...")

    conn_str = (
        "host=localhost "
        "port=5432 "
        "dbname=rakuten_amazon "
        "user=rakuten "
        "password=rakutenpass"
    )
    print("conn_str:", conn_str)

    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            row = cur.fetchone()
            print("DB version:", row[0])

    print("Done.")


if __name__ == "__main__":
    main()

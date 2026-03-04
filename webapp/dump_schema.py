import sqlite3

try:
    conn = sqlite3.connect('db.sqlite3')
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]

    with open('schema_output.md', 'w', encoding='utf-8') as f:
        f.write("## CHI TIẾT CẤU TRÚC CÁC BẢNG (SCHEMA)\n\n")
        f.write("Dưới đây là danh sách chi tiết các cột trong từng bảng của database hiện tại:\n\n")

        for table in tables:
            f.write(f"### 🔹 Bảng: `{table}`\n")
            f.write("| Tên Cột (Column) | Kiểu (Type) | Null cho phép? | Mặc định (Default) | Khóa chính (PK) |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- |\n")
            
            cursor.execute(f"PRAGMA table_info({table});")
            columns = cursor.fetchall()
            for col in columns:
                cid, name, dtype, notnull, dflt, pk = col
                allow_null = "Không" if notnull else "Có"
                pk_str = "✓" if pk else ""
                dflt_str = str(dflt) if dflt is not None else ""
                f.write(f"| **{name}** | {dtype} | {allow_null} | {dflt_str} | {pk_str} |\n")
            f.write("\n")

    conn.close()
    print("Done writing to schema_output.md")
except Exception as e:
    print(f"ERROR: {e}")

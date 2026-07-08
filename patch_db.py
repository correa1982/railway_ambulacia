import re

with open('db.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace imports
code = code.replace('import pymysql\nimport pymysql.cursors', 'import psycopg2\nimport psycopg2.extras')
code = code.replace('from pymysql import', '# from pymysql import')

# Replace connection pooling
code = code.replace('pymysql.connect', 'psycopg2.connect')
code = code.replace('cursorclass=pymysql.cursors.DictCursor', 'cursor_factory=psycopg2.extras.RealDictCursor')
code = code.replace('cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}', '# cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}')

# Remove charset and collate
code = re.sub(r' CHARACTER SET [a-zA-Z0-9_]+ COLLATE [a-zA-Z0-9_]+', '', code)

# Replace LONGTEXT with TEXT
code = code.replace('LONGTEXT', 'TEXT')

# Replace AUTO_INCREMENT with SERIAL
code = code.replace('AUTO_INCREMENT', 'SERIAL')

# Replace INSERT IGNORE
code = code.replace('INSERT IGNORE INTO', 'INSERT INTO')
code = code.replace('VALUES (?, 1)", (a,))', 'VALUES (%s, 1) ON CONFLICT DO NOTHING", (a,))')
code = code.replace('VALUES (?, 1)"', 'VALUES (%s, 1) ON CONFLICT DO NOTHING"')

# MySQLConnectionWrapper to DBConnectionWrapper
code = code.replace('MySQLConnectionWrapper', 'DBConnectionWrapper')

# Fix placeholders
code = code.replace('.replace("?", "%s")', '')
code = code.replace('mysql_query = query', 'pg_query = query.replace("?", "%s")')
code = code.replace('cursor.execute(mysql_query, params)', 'cursor.execute(pg_query, params)')

# Replace DESCRIBE and SHOW COLUMNS
code = re.sub(r'cursor\.execute\("DESCRIBE (\w+)"\)', r'cursor.execute("SELECT column_name AS \"Field\" FROM information_schema.columns WHERE table_name = \'\1\'")', code)
code = re.sub(r'cursor\.execute\("SHOW COLUMNS FROM (\w+)"\)', r'cursor.execute("SELECT column_name AS \"Field\" FROM information_schema.columns WHERE table_name = \'\1\'")', code)
code = re.sub(r'cursor = conn\.execute\(f"SHOW COLUMNS FROM \{_cl_table\}"\)', r'cursor = conn.execute(f"SELECT column_name AS \"Field\" FROM information_schema.columns WHERE table_name = \'{_cl_table}\'")', code)

# Fix SHOW INDEX
code = re.sub(r'cursor\.execute\("SHOW INDEX FROM (\w+)"\)', r'cursor.execute("SELECT indexname AS \"Key_name\" FROM pg_indexes WHERE tablename = \'\1\'")', code)

# Remove limit syntax from index creation strings
code = re.sub(r'\(255\)', '', code)

# Alter table modify column is not standard pg, need type change
code = code.replace('ALTER TABLE configuracion MODIFY COLUMN valor LONGTEXT', 'ALTER TABLE configuracion ALTER COLUMN valor TYPE TEXT')
code = code.replace('ALTER TABLE pacientes MODIFY COLUMN edad VARCHAR(50)', 'ALTER TABLE pacientes ALTER COLUMN edad TYPE VARCHAR(50)')

with open('db.py', 'w', encoding='utf-8') as f:
    f.write(code)

import sqlite3

conn = sqlite3.connect('api/bellmounth.db')
cursor = conn.cursor()

cursor.execute('SELECT COUNT(*) FROM machines')
machines = cursor.fetchone()[0]
print(f'Machines: {machines}')

cursor.execute('SELECT COUNT(*) FROM switches')
switches = cursor.fetchone()[0]
print(f'Switches: {switches}')

cursor.execute("SELECT COUNT(*) FROM users WHERE role='annoteur'")
annoteurs = cursor.fetchone()[0]
print(f'Annoteurs: {annoteurs}')

cursor.execute('SELECT COUNT(*) FROM captures')
captures = cursor.fetchone()[0]
print(f'Captures: {captures}')

conn.close()

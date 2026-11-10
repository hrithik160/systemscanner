p = r'C:\Users\tms_s\AppData\Local\Temp\rd_sandbox_j3a49_16\workspace\backend\app\main.py'
c = open(p, encoding='utf-8').read()
print('Has root route /:', '@app.get("/")' in c or "@app.get('/')" in c)
for r in ['campus.router', 'navigation.router', 'qr.router']:
    print(r, 'included:', r in c)

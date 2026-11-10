import os
base = r'C:\Users\tms_s\AppData\Local\Temp\rd_sandbox_projects'
for root, dirs, files in os.walk(base):
    dirs[:] = [d for d in dirs if d not in ('node_modules', '.git', 'dist')]
    for f in files:
        if f == 'App.jsx':
            p = os.path.join(root, f)
            c = open(p, encoding='utf-8', errors='ignore').read()
            if 'Message is' in c:
                print('Found in:', p)

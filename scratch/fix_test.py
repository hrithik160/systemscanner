with open("release-domino/backend/tests/test_graph_twopass.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('"required": true', '"required": false')

with open("release-domino/backend/tests/test_graph_twopass.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated test_graph_twopass.py successfully")

with open ("manifest5.xml", "r") as file:
    x = file.readlines()

newLines = []
for line in x:
    if "<c" in line:
        continue
    newLines.append(line)
with open("manifest5.xml", "w") as file:
    file.writelines(newLines)
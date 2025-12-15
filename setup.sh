#!/bin/bash
# setup.sh - התקנת subrecon.py ככלי מערכתי

set -e

echo "========================================"
echo "Installing subrecon.py system-wide"
echo "========================================"

# בדיקה אם הסקריפט רץ כ-root
if [ "$EUID" -eq 0 ]; then 
    echo "[!] Warning: Running as root/sudo"
fi

# יצירת תיקייה לסקריפטים
INSTALL_DIR="/usr/local/bin"
CONFIG_DIR="$HOME/.subrecon"

echo "[*] Creating directories..."
mkdir -p "$CONFIG_DIR"

# בדיקת Python
echo "[*] Checking Python version..."
python3 --version > /dev/null 2>&1 || { echo "[-] Python3 not found!"; exit 1; }

# התקנת תלויות
echo "[*] Installing dependencies..."
pip3 install --upgrade pip
pip3 install requests beautifulsoup4 dnspython colorama tqdm

# יצירת קובץ התקנה בספריית מערכת
echo "[*] Creating system-wide script..."

cat > /tmp/subrecon_wrapper.py << 'EOF'
#!/usr/bin/env python3
"""
Wrapper script for subrecon.py that finds the main script
"""

import os
import sys

# חיפוש הקובץ במקומות אפשריים
possible_paths = [
    os.path.join(os.path.dirname(__file__), 'subrecon.py'),
    os.path.join('/usr/local/share/subrecon', 'subrecon.py'),
    os.path.join(os.path.expanduser('~'), '.subrecon', 'subrecon.py'),
    os.path.join(os.getcwd(), 'subrecon.py'),
    'subrecon.py'
]

found = False
for path in possible_paths:
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                # בדיקה שזה באמת הקובץ שלנו
                content = f.read()
                if 'subrecon.py' in content and 'SubdomainEnumerator' in content:
                    script_path = path
                    found = True
                    break
        except:
            continue

if not found:
    print("[-] Error: Could not find subrecon.py!")
    print("[*] Looking in:", possible_paths)
    sys.exit(1)

# הרצת הקובץ המקורי
exec(open(script_path).read())

if __name__ == "__main__":
    # אם הקוד לא כולל קריאה ל-main
    import subrecon_main
EOF

# אם קובץ subrecon.py נמצא בתיקייה הנוכחית
if [ -f "subrecon.py" ]; then
    echo "[*] Found subrecon.py in current directory"
    
    # העתקת הקובץ לתיקיית התקנה
    sudo cp "subrecon.py" "/usr/local/bin/subrecon.py" 2>/dev/null || \
    cp "subrecon.py" "/usr/local/bin/subrecon.py"
    
    # יצירת קובץ הרצה bash
    cat > /tmp/subrecon << 'EOF'
#!/bin/bash
# Wrapper script for subrecon.py

# חיפוש הקובץ
if [ -f "/usr/local/bin/subrecon.py" ]; then
    SCRIPT="/usr/local/bin/subrecon.py"
elif [ -f "$HOME/.subrecon/subrecon.py" ]; then
    SCRIPT="$HOME/.subrecon/subrecon.py"
elif [ -f "./subrecon.py" ]; then
    SCRIPT="./subrecon.py"
else
    echo "[-] Error: subrecon.py not found!"
    echo "[*] Install it with: sudo bash setup.sh"
    exit 1
fi

# הרצה עם python3
python3 "$SCRIPT" "$@"
EOF
    
    # מתן הרשאות הרצה והעברה
    chmod +x /tmp/subrecon
    sudo mv /tmp/subrecon "$INSTALL_DIR/subrecon" 2>/dev/null || \
    mv /tmp/subrecon "$HOME/.local/bin/subrecon" 2>/dev/null || \
    { echo "[*] Moving to /tmp/subrecon - you need to manually copy it"; mv /tmp/subrecon /tmp/subrecon_bin; }
    
    # גם שומר עותק בתיקיית המשתמש
    cp "subrecon.py" "$CONFIG_DIR/subrecon.py"
    
    echo "[+] Installed subrecon.py to:"
    echo "    - /usr/local/bin/subrecon (executable)"
    echo "    - /usr/local/bin/subrecon.py (main script)"
    echo "    - $CONFIG_DIR/subrecon.py (user copy)"
    
else
    echo "[-] Error: subrecon.py not found in current directory!"
    echo "[*] Please run this script from the directory containing subrecon.py"
    exit 1
fi

# יצירת alias עבור .bashrc
echo "[*] Setting up aliases..."

# בדיקה אם יש .bashrc או .zshrc
SHELL_RC=""
if [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
elif [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bash_profile" ]; then
    SHELL_RC="$HOME/.bash_profile"
fi

if [ -n "$SHELL_RC" ]; then
    # בדיקה אם כבר יש alias
    if ! grep -q "alias subrecon=" "$SHELL_RC"; then
        echo "" >> "$SHELL_RC"
        echo "# Subdomain enumeration tool" >> "$SHELL_RC"
        echo "alias subrecon='python3 ~/.subrecon/subrecon.py'" >> "$SHELL_RC"
        echo "[+] Added alias to $SHELL_RC"
    fi
    
    # הוספת PATH אם צריך
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
        echo "[+] Added ~/.local/bin to PATH"
    fi
fi

# יצירת קובץ uninstall
cat > "$CONFIG_DIR/uninstall.sh" << 'EOF'
#!/bin/bash
# Uninstall script for subrecon

echo "Uninstalling subrecon..."

# הסרת קבצים מ-/usr/local/bin
sudo rm -f /usr/local/bin/subrecon 2>/dev/null
sudo rm -f /usr/local/bin/subrecon.py 2>/dev/null

# הסרת קבצים מ-~/.local/bin
rm -f ~/.local/bin/subrecon 2>/dev/null

# הסרת alias מ-.bashrc/.zshrc
if [ -f ~/.bashrc ]; then
    sed -i '/alias subrecon=/d' ~/.bashrc
    sed -i '/# Subdomain enumeration tool/d' ~/.bashrc
fi

if [ -f ~/.zshrc ]; then
    sed -i '/alias subrecon=/d' ~/.zshrc
    sed -i '/# Subdomain enumeration tool/d' ~/.zshrc
fi

# הסרת תיקיית הקונפיגורציה
rm -rf ~/.subrecon

echo "Done! You may need to restart your terminal."
EOF

chmod +x "$CONFIG_DIR/uninstall.sh"

echo ""
echo "========================================"
echo "Installation complete!"
echo "========================================"
echo ""
echo "Usage:"
echo "  subrecon example.com"
echo "  subrecon example.com -o results.txt"
echo "  subrecon example.com --fast"
echo ""
echo "To update:"
echo "  1. Replace subrecon.py in current directory"
echo "  2. Run: sudo bash setup.sh"
echo ""
echo "To uninstall:"
echo "  bash ~/.subrecon/uninstall.sh"
echo ""
echo "Reload your shell or run:"
echo "  source $SHELL_RC"
echo "========================================"

#!/bin/bash
# install.sh - התקנה פשוטה של subrecon

echo "[*] Installing subrecon..."

# בדיקת Python
if ! command -v python3 &> /dev/null; then
    echo "[-] Python3 is required!"
    exit 1
fi

# התקנת תלויות
echo "[*] Installing Python dependencies..."
pip3 install requests beautifulsoup4 dnspython colorama tqdm > /dev/null 2>&1

# יצירת תיקיית התקנה
INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"
mkdir -p "$HOME/.subrecon"

# העתקת הקובץ הנוכחי
if [ -f "subrecon.py" ]; then
    # שמירת עותק
    cp "subrecon.py" "$HOME/.subrecon/subrecon.py"
    
    # יצירת סקריפט הרצה
    cat > "$INSTALL_DIR/subrecon" << 'EOF'
#!/bin/bash
python3 "$HOME/.subrecon/subrecon.py" "$@"
EOF
    
    chmod +x "$INSTALL_DIR/subrecon"
    
    echo "[+] Installed to: $INSTALL_DIR/subrecon"
    echo "[+] Config directory: $HOME/.subrecon/"
    
    # הוספת PATH אם צריך
    if [[ ! ":$PATH:" == *":$INSTALL_DIR:"* ]]; then
        echo ""
        echo "[!] Add to PATH by adding this to your ~/.bashrc or ~/.zshrc:"
        echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo ""
        echo "Then run: source ~/.bashrc"
    fi
    
    echo ""
    echo "[+] Installation complete!"
    echo "[*] Usage: subrecon example.com"
    
else
    echo "[-] Error: subrecon.py not found!"
    echo "[*] Run this script from the directory containing subrecon.py"
    exit 1
fi

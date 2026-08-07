# Sol Cesto Gold Editor

A simple Python script to view and modify your gold.

## Usage

### 1. Download the script

Download `sc_gold.py` and place it wherever you'd like.

### 2. View your current gold

```powershell
python sc_gold.py show "$env:LOCALAPPDATA\SolCesto\EBWebView\Default\IndexedDB\https_app.localhost_0.indexeddb.leveldb"
```

This will display your current amount of gold stored in the save file.

### 3. Set a new gold amount

```powershell
python sc_gold.py set "$env:LOCALAPPDATA\SolCesto\EBWebView\Default\IndexedDB\https_app.localhost_0.indexeddb.leveldb" 50000
```

Replace `50000` with any amount of gold you want.

---

## Example

```powershell
python sc_gold.py set "$env:LOCALAPPDATA\SolCesto\EBWebView\Default\IndexedDB\https_app.localhost_0.indexeddb.leveldb" 999999
```

Your save file will now contain **999,999 gold**.

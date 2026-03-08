import subprocess
import time

from code_file_io import load_codes_from_file

ADB_PATH = "C:\\Users\\szymo\\AppData\\Local\\Android\\Sdk\\platform-tools\\adb.exe"

def get_scan():
    try:       
        process = subprocess.Popen(
            [ADB_PATH, "logcat", "-d", "-t", "1", "-b", "main", "-v", "raw", "-s", "QR_EMU:D"],
            stdout=subprocess.PIPE,
            text=True
        )
            
        line = process.stdout.read().strip() # Get the most recent line
        if line:
            return line.splitlines()[-1]  # Return the last line (most recent log)
        else:
            return

    except Exception as e:
        print("ADB error:", e)
        return ""



if __name__ == "__main__":
    codes = load_codes_from_file("codes.txt")

    print(f"Loaded {len(codes)} codes")

    # example lookup
    test_code = list(codes.keys())[0]

    print("Example code:", test_code)
    print("Entry:", codes[test_code])
    
    last_code = ""
    print("Waiting for scans...")
    while True:
        code = get_scan()

        if code and codes[code]["used"] == False and code != last_code:
            print("SCANNED:", code)
            last_code = code
            codes[code]["used"] = True

        time.sleep(1)
        

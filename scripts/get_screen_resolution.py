import ctypes

if __name__ == "__main__":
    user32 = ctypes.windll.user32
    print(str(user32.GetSystemMetrics(0)) + "x" + str(user32.GetSystemMetrics(1)))

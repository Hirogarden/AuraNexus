# This is a tiny stub used by the launcher during development when koboldcpp submodule is not present.
# Replace with actual koboldcpp executable invocation when submodule is added.
import time
print('koboldcpp stub started')
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print('koboldcpp stub exiting')

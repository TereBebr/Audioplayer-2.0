import utils
import time
p = utils.create_player("http://127.0.0.1:8000/server/stream/1", 35)
p.play(); time.sleep(3)
p.set_time(60000); time.sleep(3)
print(p.get_time(), p.get_length())
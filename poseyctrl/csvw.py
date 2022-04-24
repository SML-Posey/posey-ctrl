import time
import queue
import signal

from multiprocess import Queue, Process

class CSVWriterLogger:
    def info(self, msg):
        print(f'CSVWriter: [INFO] {msg}')
    def warning(self, msg):
        print(f'CSVWriter: [WARNING] {msg}')
    def error(self, msg):
        print(f'CSVWriter: [ERROR] {msg}')

class CSVWriter:
    def __init__(self, qin: Queue):
        self.log = CSVWriterLogger()

        self.process = None
        self.qin = qin

        self.files = {}

    def exit_gracefully(self, *args):
        self.log.info('Terminating...')
        self.qin.put(('quit',))

    def close(self):
        for id in self.files:
            if self.files[id] is not None:
                self.files[id].close()
        self.files = {}

    def loop(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        while True:
            # Handle next message.
            try:
                msg = self.qin.get_nowait()
                sig = msg[0]
                if sig == 'quit':
                    self.close()
                    break

                else:
                    sig, t, data = msg
                    if sig not in self.files:
                        self.files[sig] = open(f'data.{sig}.csv', 'w')
                        self.files[sig].write('pctime,' + ','.join(data.keys()) + '\n')
                    self.files[sig].write('"' + str(t) + '",' + ','.join([str(x) for x in data.values()]) + '\n')

            except queue.Empty:
                time.sleep(1)
        self.log.info('Finished loop.')

    def start(self):
        self.stop()
        self.log.info('Starting process...')
        self.process = Process(target=CSVWriter.loop, args=(self,))
        self.process.start()
        self.log.info('Returning control.')

    def stop(self):
        if self.process is not None and self.process.is_alive():
            self.log.info('Stopping process...')
            self.process.terminate()
            self.log.info('Joining...')
            self.process.join(1)
            self.process = None
            self.log.info('Shutdown complete')
        else:
            self.process = None

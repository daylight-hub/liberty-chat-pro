import RNS
import socket
import threading
import traceback
import time

# Define the Sideband service plugin class
class TAKReticulumBridge(SidebandServicePlugin):
    # Name of the service as it will be registered in Sideband
    service_name = "tak_reticulum_bridge"

    # This thread listens for multicast UDP (TAK COT) and sends to Reticulum
    def uplink(self):
        try:
            RNS.log("Uplink thread active.")
            while self.should_run:
                try:
                    # Receive data from multicast socket
                    data, addr = self.sock.recvfrom(1500)
                    RNS.log(f"[Uplink] Received from {addr}, broadcasting to Reticulum")

                    # Log as UTF-8 XML
                    try:
                        RNS.log(f"[Uplink] XML:\n{data.decode('utf-8', errors='replace')}")
                    except Exception as decode_err:
                        RNS.log(f"[Uplink] Failed to decode XML: {decode_err}")

                    # Create a Reticulum packet to broadcast
                    packet = RNS.Packet(self.broadcast_destination, data)
                    packet.send()

                except Exception as inner_e:
                    RNS.log(f"[Uplink] Error: {inner_e}")
                    RNS.log(traceback.format_exc())

        except Exception as e:
            RNS.log("CRITICAL: uplink thread failed to start.")
            RNS.log(traceback.format_exc())

    # This thread receives packets from Reticulum and re-broadcasts over UDP multicast
    def downlink(self):
        try:
            def receive(data, packet):
                try:
                    RNS.log(f"[Downlink] Received from Reticulum, forwarding to {self.group}:{self.port}")
                    try:
                        RNS.log(f"[Downlink] XML:\n{data.decode('utf-8', errors='replace')}")
                    except Exception as decode_err:
                        RNS.log(f"[Downlink] Failed to decode XML: {decode_err}")
                    self.sock.sendto(data, (self.group, self.port))
                except Exception as e:
                    RNS.log(f"[Downlink] Error: {e}")
                    RNS.log(traceback.format_exc())

            self.broadcast_destination.set_packet_callback(receive)

            while self.should_run:
                time.sleep(1)

            RNS.log("Downlink listener thread exiting.")

        except Exception as e:
            RNS.log("CRITICAL: downlink thread failed to start.")
            RNS.log(traceback.format_exc())

    def service_jobs(self):
        try:
            RNS.log("TAK to Reticulum Bridge initializing...")

            if not hasattr(RNS.Transport, "owner") or RNS.Transport.owner is None:
                try:
                    RNS.Transport.owner = RNS.Reticulum.get_instance()
                except Exception:
                    RNS.log("[TAK Bridge] Reticulum already running. Proceeding with existing instance.")

            group = "239.2.3.1"
            port = 6969
            interface = "0.0.0.0"

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.bind((interface, port))
            mreq = socket.inet_aton(group) + socket.inet_aton(interface)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

            self.sock = sock
            self.group = group
            self.port = port

            self.broadcast_destination = RNS.Destination(
                None,
                RNS.Destination.IN,
                RNS.Destination.PLAIN,
                "atak_bridge",
                "broadcast"
            )

            self.uplink_thread = threading.Thread(target=self.uplink, daemon=True)
            self.downlink_thread = threading.Thread(target=self.downlink, daemon=True)
            self.uplink_thread.start()
            self.downlink_thread.start()

            while self.should_run:
                time.sleep(1)

            RNS.log("TAK to Reticulum Bridge threads exiting cleanly.")

        except Exception as outer_e:
            RNS.log("CRITICAL: Failed to start TAK to Reticulum Bridge.")
            RNS.log(traceback.format_exc())

    def start(self):
        try:
            RNS.log("Starting TAK to Reticulum service plugin...")
            if not hasattr(RNS.Transport, "owner") or RNS.Transport.owner is None:
                try:
                    RNS.Transport.owner = RNS.Reticulum.get_instance()
                except Exception:
                    RNS.log("[TAK Bridge] Reticulum already running. Proceeding with existing instance.")
            self.should_run = True
            self.service_thread = threading.Thread(target=self.service_jobs, daemon=True)
            self.service_thread.start()
            super().start()
        except Exception as e:
            RNS.log(f"Error during start(): {e}")
            RNS.log(traceback.format_exc())

    def stop(self):
        self.should_run = False
        super().stop()

plugin_class = TAKReticulumBridge

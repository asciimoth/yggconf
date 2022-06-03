# Yggconf by DomesticMoth
#
# To the extent possible under law, the person who associated CC0 with
# yggconf has waived all copyright and related or neighboring rights
# to yggconf.
#
# You should have received a copy of the CC0 legalcode along with this
# work.  If not, see <http://creativecommons.org/publicdomain/zero/1.0/>.
import json
import typing
import urllib.error
import urllib.parse
import urllib.request
from email.message import Message
import urllib.parse
import socket
import re
import subprocess


URI_REGEX = r"[tls]://(?:[-\w.]|(?:%[\da-fA-F]{2}))+"
PEERS_LIST_URL = "https://raw.githubusercontent.com/DomesticMoth/MPL/main/yggdrasil.txt"


# Http request logic without requests lib
# Stolen from https://dev.to/bowmanjd/http-calls-in-python-without-requests-or-other-external-dependencies-5aj1
class Response(typing.NamedTuple):
    body: str
    headers: Message
    status: int
    error_count: int = 0

    def json(self) -> typing.Any:
        """
        Decode body's JSON.

        Returns:
            Pythonic representation of the JSON object
        """
        try:
            output = json.loads(self.body)
        except json.JSONDecodeError:
            output = ""
        return output


def request(
    url: str,
    data: dict = None,
    params: dict = None,
    headers: dict = None,
    method: str = "GET",
    data_as_json: bool = True,
    error_count: int = 0,
) -> Response:
    if not url.casefold().startswith("http"):
        raise urllib.error.URLError("Incorrect and possibly insecure protocol in url")
    method = method.upper()
    request_data = None
    headers = headers or {}
    data = data or {}
    params = params or {}
    headers = {"Accept": "application/json", **headers}

    if method == "GET":
        params = {**params, **data}
        data = None

    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True, safe="/")

    if data:
        if data_as_json:
            request_data = json.dumps(data).encode()
            headers["Content-Type"] = "application/json; charset=UTF-8"
        else:
            request_data = urllib.parse.urlencode(data).encode()

    httprequest = urllib.request.Request(
        url, data=request_data, headers=headers, method=method
    )

    try:
        with urllib.request.urlopen(httprequest) as httpresponse:
            response = Response(
                headers=httpresponse.headers,
                status=httpresponse.status,
                body=httpresponse.read().decode(
                    httpresponse.headers.get_content_charset("utf-8")
                ),
            )
    except urllib.error.HTTPError as e:
        response = Response(
            body=str(e.reason),
            headers=e.headers,
            status=e.code,
            error_count=error_count + 1,
        )

    return response


def fetch_peers():
    resp = request(PEERS_LIST_URL, )
    if resp.status != 200:
        raise Exception("Cannot get peers list; status code: {}".format(resp.status))
    peers = []
    for row in resp.body.split("\n"):
        if len(row) == 0:
            continue
        if row[0] == "#":
            continue
        peers.append(row)
    return peers

def extract_addrs(peers):
    addrs = []
    for peer in peers:
        parsed_url = urllib.parse.urlparse(peer)
        try:
            addrs.append((peer, socket.gethostbyname(parsed_url.hostname)))
        except:
            pass
    return addrs

def deduplicate(addrs):
    ret = {}
    for addr in addrs:
        key = addr[1]
        if key in ret:
            old_sheme = ret[key][0][:3]
            new_sheme = addr[0][:3]
            if new_sheme == "tls" and old_sheme == "tcp":
                ret[key] = addr
        else:
            ret[key] = addr
    return ret.values()

def ping(addr) -> float:
    cmd = "ping {} -c 2 -w 4 -W 2".format(addr)
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    out = proc.stdout.read().decode("utf-8")
    pings = [int(float(p)) for p in re.findall(r"time=(\d+(?:\.\d+)?)", out)]
    if len(pings) < 1:
        return 100000000
    return int(sum(pings)/len(pings))

def check(addrs):
    ret = []
    for addr in addrs:
        p = ping(addr[1])
        if p < 300:
            ret.append((addr[0], p))
    ret.sort(key=lambda x: x[1])
    return ret

def get_peers(count: int):
    return [peer[0] for peer in  check(deduplicate(extract_addrs(fetch_peers())))[:count] ]

def multireplace(string, repl) -> str:
    if len(string) < 1:
        return ""
    ret = ""
    start = 0
    end = len(string)
    for i in range(len(repl)):
        if i < len(repl)-1:
            end = repl[i+1][0]
        else:
            end = len(string)
        r = repl[i]
        ret += string[start:r[0]+1]
        ret += r[2]
        start = r[1]+1
    ret += string[start:]
    return ret

def add_peers(config, extra):
    repl = []
    for sub in re.finditer(r"[\s|^|{]Peers:[\s|\n]*\[[\s|\n|\w|/|:|.|,|'|\"|\?|=|-]*]", config):
        #result += EXAMPLE_CONFIG[start:sub.start()]+"Peers: ["
        #print(sub)
        #print(EXAMPLE_CONFIG[sub.start():sub.end()])
        #print(re.sub(r"\s+", " ", re.sub(r"[\n|\[|\]|'|\"]", " ", sub.group()).replace("Peers:", " ")).split(" "))
        #result += EXAMPLE_CONFIG[sub.end():]+"]"
        already_exist_peers = extra.copy()
        for peer in re.sub(r"\s+", " ", re.sub(r"[\n|\[|\]|'|\"|,]", " ", sub.group()).replace("Peers:", " ")).split(" "):
            if len(peer) == 0:
                continue
            already_exist_peers.append(peer)
        already_exist_peers = list(set(already_exist_peers))
        peers = ""
        for peer in already_exist_peers:
            peers += peer+"\n"
        repl.append((sub.start(), sub.end(), "Peers:[\n"+peers+"]\n"))
    return multireplace(config, repl)

EXAMPLE_CONFIG = """
{
  # List of connection strings for outbound peer connections in URI format,
  # e.g. tls://a.b.c.d:e or socks://a.b.c.d:e/f.g.h.i:j. These connections
  # will obey the operating system routing table, therefore you should
  # use this section when you may connect via different interfaces.
  Peers: [
    tls://ygg-fin.incognet.io:8884
    tls://ygg-fin.incognet.io:8885
    tls://ygg.tomasgl.ru:61944?key=c5e0c28a600c2118e986196a0bbcbda4934d8e9278ceabea48838dc5d8fae576
  ]

  # List of connection strings for outbound peer connections in URI format,
  # arranged by source interface, e.g. { "eth0": [ tls://a.b.c.d:e ] }.
  # Note that SOCKS peerings will NOT be affected by this option and should
  # go in the "Peers" section instead.
  InterfacePeers: {}
  
  # Listen addresses for incoming connections. You will need to add
  # listeners in order to accept incoming peerings from non-local nodes.
  # Multicast peer discovery will work regardless of any listeners set
  # here. Each listener should be specified in URI format as above, e.g.
  # tls://0.0.0.0:0 or tls://[::]:0 to listen on all interfaces.
  Listen: []

  # Listen address for admin connections. Default is to listen for local
  # connections either on TCP/9001 or a UNIX socket depending on your
  # platform. Use this value for yggdrasilctl -endpoint=X. To disable
  # the admin socket, use the value "none" instead.
  AdminListen: tcp://localhost:9001

  # Configuration for which interfaces multicast peer discovery should be
  # enabled on. Each entry in the list should be a json object which may
  # contain Regex, Beacon, Listen, and Port. Regex is a regular expression
  # which is matched against an interface name, and interfaces use the
  # first configuration that they match gainst. Beacon configures whether
  # or not the node should send link-local multicast beacons to advertise
  # their presence, while listening for incoming connections on Port.
  # Listen controls whether or not the node listens for multicast beacons
  # and opens outgoing connections.
  MulticastInterfaces:
  [
    {
      Regex: .*
      Beacon: true
      Listen: true
      Port: 0
    }
  ]

  # List of peer public keys to allow incoming peering connections
  # from. If left empty/undefined then all connections will be allowed
  # by default. This does not affect outgoing peerings, nor does it
  # affect link-local peers discovered via multicast.
  AllowedPublicKeys: []

  # Your public key. Your peers may ask you for this to put
  # into their AllowedPublicKeys configuration.
  PublicKey: AAAAAAAAAAAAa

  # Your private key. DO NOT share this with anyone!
  PrivateKey: AAAAAAAAAAAAAAAAAAa

  # Local network interface name for TUN adapter, or "auto" to select
  # an interface automatically, or "none" to run without TUN.
  IfName: Yggdrasil

  # Maximum Transmission Unit (MTU) size for your local TUN interface.
  # Default is the largest supported size for your platform. The lowest
  # possible value is 1280.
  IfMTU: 65535

  # By default, nodeinfo contains some defaults including the platform,
  # architecture and Yggdrasil version. These can help when surveying
  # the network and diagnosing network routing problems. Enabling
  # nodeinfo privacy prevents this, so that only items specified in
  # "NodeInfo" are sent back if specified.
  NodeInfoPrivacy: false

  # Optional node info. This must be a { "key": "value", ... } map
  # or set as null. This is entirely optional but, if set, is visible
  # to the whole network on request.
  NodeInfo: {}
}

"""[1:-1]


if __name__ == "__main__":
    print(add_peers(EXAMPLE_CONFIG, []))

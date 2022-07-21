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
import time
import os
import sys


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

def select_tls(peers):
    ret = []
    for peer in peers:
        if peer.startswith("tls://") or peer.endswith(":443"):
            ret.append(peer)
    return ret

def get_peers(count: int, ptls: bool):
    all_peers = [peer[0] for peer in check(deduplicate(extract_addrs(fetch_peers())))]
    ret = []
    if ptls:
        ret = select_tls(all_peers)[:count]
    else:
        ret = all_peers[:count]
    return ret

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

def update_config(src, dst, peers_count, ptls):
    peers = get_peers(peers_count, ptls)
    raw = ""
    with open(src, "r") as f:
        raw = f.read()
    result = add_peers(raw, peers)
    with open(dst, "w") as f:
        f.write(result)

# Every $delay seconds
# read $src file
# add $count nearest peers to it
# write to $dst file
# and then run $cmd shell command
# The ptls flag enables preference for connection on port 443 over the tls protocol
def loop(src, dst, count, delay, cmd, ptls):
    while True:
        update_config(src,dst, count, ptls)
        os.system(cmd)
        time.sleep(delay)

def get_bool_arg(nom: int) -> bool:
    try:
        return sys.argv[nom].lower() == "true"
    except:
        return False

if __name__ == "__main__":
    loop(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], get_bool_arg(6))

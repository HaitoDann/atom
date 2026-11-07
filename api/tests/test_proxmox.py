import asyncio

import httpx

from app import proxmox


def _fake(status_guest="running", cpu=0.2):
    def handler(req: httpx.Request):
        assert req.headers["authorization"] == "PVEAPIToken=atom@pve!atom=secret"
        if req.url.path.endswith("/cluster/resources"):
            return httpx.Response(200, json={"data": [
                {"type": "node", "node": "pve", "status": "online", "cpu": cpu, "mem": 8e9, "maxmem": 32e9, "disk": 20e9, "maxdisk": 100e9, "uptime": 90000, "maxcpu": 8},
                {"type": "lxc", "vmid": 101, "name": "atom", "node": "pve", "status": status_guest, "cpu": 0.1, "mem": 2e9, "maxmem": 4e9, "uptime": 3600, "maxcpu": 4},
                {"type": "qemu", "vmid": 9000, "name": "modele", "node": "pve", "status": "stopped", "template": 1},
                {"type": "storage", "storage": "local-lvm", "node": "pve", "status": "available", "disk": 90e9, "maxdisk": 100e9, "plugintype": "lvmthin"},
            ]})
        return httpx.Response(200, json={"data": {"loadavg": ["0.5", "0.4", "0.3"], "cpuinfo": {"model": "Ryzen"}, "pveversion": "pve-manager/8"}})
    return handler


def test_proxmox_monitoring(monkeypatch, client):
    sent = []
    monkeypatch.setattr(proxmox, "URL", "https://pve:8006")
    monkeypatch.setattr(proxmox, "TOKEN_ID", "atom@pve!atom")
    monkeypatch.setattr(proxmox, "TOKEN_SECRET", "secret")

    async def fake_notify(title, body):
        sent.append(title)

    monkeypatch.setattr(proxmox, "_notify", fake_notify)
    proxmox.save_settings({"minutes": 0, "cpu": 90})
    orig = httpx.AsyncClient

    def use(handler):
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: orig(transport=httpx.MockTransport(handler), **{k: v for k, v in kw.items() if k != "verify"}))

    use(_fake())
    asyncio.run(proxmox.poll())
    st = proxmox.state
    assert st["ok"] and st["nodes"][0]["mem"] == 25.0 and [g["id"] for g in st["guests"]] == [101]   # modèle ignoré
    asyncio.run(proxmox.evaluate())
    assert any("Stockage local-lvm" in t for t in sent)          # 90 % ≥ 85 %
    text = proxmox.summary()
    assert "LXC 101 atom" in text and "Nœud pve" in text
    assert proxmox.wants("Comment va le serveur ?") and not proxmox.wants("Bonjour")

    use(_fake(cpu=0.97))
    asyncio.run(proxmox.poll()); asyncio.run(proxmox.evaluate())
    assert any("Processeur de pve" in t for t in sent)

    use(_fake(status_guest="stopped"))
    asyncio.run(proxmox.poll()); asyncio.run(proxmox.evaluate())
    assert any("LXC 101 (atom) arrêtée" in t for t in sent)
    use(_fake(status_guest="running"))
    asyncio.run(proxmox.poll()); asyncio.run(proxmox.evaluate())
    assert any(t.startswith("✓ Rétabli") and "LXC 101" in t for t in sent)

    r = client.get("/api/proxmox").json()
    assert r["configured"] and r["nodes"][0]["name"] == "pve"

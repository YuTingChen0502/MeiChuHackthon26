"""Logical presentation handles; grouping never certifies physical identity."""
import hashlib
import re
import sys
from types import SimpleNamespace


def _name(value):
    return re.sub(r"[^\w]", "", value.casefold())


def _priority(endpoint):
    host=endpoint.host_api.casefold()
    order=("wasapi","directsound","mme") if sys.platform=="win32" else ("pipewire","pulse","alsa","jack")
    return (next((i for i,label in enumerate(order) if label in host),len(order)),endpoint.device_id)


class MicrophoneInventory:
    def __init__(self,backend):
        self.backend=backend
        self.raw=[SimpleNamespace(device_id=d.device_id,name=getattr(d,"name","Microphone"),
            host_api=getattr(d,"host_api","unknown"),is_default=getattr(d,"is_default",None)) for d in backend.discover()]
        self.candidates={}
        self.microphones=[]
        defaults=getattr(backend,"default_inputs",lambda:[])()
        default_ids=set(defaults) or {d.device_id for d in self.raw if getattr(d,"is_default",False)}
        default=[d for d in self.raw if d.device_id in default_ids]
        if default:
            self._add("system-default","Default microphone",default,"system_default","system_route",True)
        groups=[]
        for endpoint in sorted(self.raw,key=_priority):
            normalized=_name(endpoint.name)
            # Generic OS route aliases are represented by system-default, not as
            # additional alleged physical microphones. Keep them in raw diagnostics.
            if any(term in endpoint.name.casefold() for term in ("sound mapper","primary sound capture","音效對應表","主要音效擷取")):
                if endpoint not in default: default.append(endpoint)
                continue
            possible=[group for group in groups if all(d.host_api != endpoint.host_api for d in group)
                and any(_name(d.name)==normalized or
                    (min(len(normalized),len(_name(d.name)))>=20 and
                     (normalized.startswith(_name(d.name)) or _name(d.name).startswith(normalized))) for d in group)]
            if len(possible)==1:possible[0].append(endpoint)
            else:groups.append([endpoint])
        for group in groups:
            chosen=sorted(group,key=_priority)[0]
            identity="mic:"+hashlib.sha256(chosen.device_id.encode()).hexdigest()[:20]
            self._add(identity,chosen.name,group,"logical_group" if len(group)>1 else "endpoint",
                "name_heuristic" if len(group)>1 else "none",True if any(d.device_id in default_ids for d in group) else None)
        repeated={m["name"] for m in self.microphones if sum(x["name"]==m["name"] for x in self.microphones)>1}
        for name in repeated:
            for number,item in enumerate((m for m in self.microphones if m["name"]==name),1):
                item["name"]=f"{name} (input {number})"
        if default and "system-default" not in self.candidates:
            self._add("system-default","Default microphone",default,"system_default","system_route",True)
        elif default:self.candidates["system-default"]=sorted(default,key=_priority)
        self.default_microphone_id="system-default" if "system-default" in self.candidates else None

    def _add(self,identity,name,group,kind,basis,default):
        self.candidates[identity]=sorted(group,key=_priority)
        self.microphones.append(dict(microphone_id=identity,name=name,is_default=default,selection_kind=kind,grouping=basis))

    def resolve(self,identity):
        if identity in self.candidates:
            return self.candidates[identity]
        # Exact saved native handles remain resolvable; no stale numeric index reuse.
        return [d for d in self.raw if d.device_id==identity]

    def name(self,identity):
        return next((m["name"] for m in self.microphones if m["microphone_id"]==identity),
                    next((d.name for d in self.raw if d.device_id==identity),identity))

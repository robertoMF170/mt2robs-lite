# -*- coding: utf-8 -*-
# ============================================================================
# ZoneGuard -- zonas MORTAS (vermelhas) e LIVRES (verdes) por mapa.
#
# O ficheiro de zonas e criado pela ferramenta do PC "marcar_zonas.py" e fica
# em:  MT2Robs/Saves/zones_<mapa>.txt
# As coordenadas gravadas sao do MUNDO (as mesmas unidades do
# player.GetMainCharacterPosition()), uma por linha:
#     D x1,y1,x2,y2   -> zona MORTA (vermelha): o bot NUNCA anda aqui
#     F x1,y1,x2,y2   -> zona LIVRE (verde): sempre ok (preferencia)
# Linhas com # sao comentarios (o marcar_zonas.py guarda a calibracao la).
#
# Regras de movimento:
#   - dentro de MORTA             -> PROIBIDO (waypoints nao sao gravados,
#                                    sao saltados no replay, spots/wander/
#                                    escape nunca escolhem la)
#   - dentro de LIVRE             -> permitido (usado como preferencia nos
#                                    pontos aleatorios)
#   - NAO MARCADO (entre zonas)   -> permitido
# Sem ficheiro de zonas para o mapa -> tudo permitido (comportamento antigo).
# ============================================================================

import sys

try:
    import eXLib
    ZONES_PATH = eXLib.PATH + 'MT2Robs/Saves/zones_%s.txt'
except:
    ZONES_PATH = 'MT2Robs/Saves/zones_%s.txt'

try:
    import math as _m
except:
    _m = None

# cache por mapa (so re-le o ficheiro quando o mapa muda)
_loaded_map = [None]
_dead = []   # [(x1, y1, x2, y2)] em coordenadas do mundo
_free = []

STEP = 120.0   # passo de amostragem dos segmentos (unidades do mundo)


def _ub_log(text):
    try:
        from datetime import datetime
        stamp = datetime.now().strftime('%H:%M:%S')
        try:
            p = eXLib.PATH + 'syserr_ub.txt'
        except:
            p = 'syserr_ub.txt'
        f = open(p, 'a')
        f.write('[%s] %s\n' % (stamp, text))
        f.close()
    except:
        pass


def _load(mapname):
    global _loaded_map, _dead, _free
    mapname = str(mapname)
    if _loaded_map[0] == mapname:
        return
    _loaded_map[0] = mapname
    _dead = []
    _free = []
    try:
        for line in open(ZONES_PATH % mapname, 'r'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.replace(',', ' ').split()
            if len(parts) != 5:
                continue
            typ = parts[0].upper()
            try:
                x1, y1, x2, y2 = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
            except:
                continue
            r = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            if typ == 'D':
                _dead.append(r)
            elif typ == 'F':
                _free.append(r)
        _ub_log('[ZoneGuard] %s: %d zona(s) MORTA(S) + %d LIVRE(S) carregadas' % (
            mapname, len(_dead), len(_free)))
    except:
        pass


def _inRect(x, y, r):
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


def HasZones(mapname):
    """True se o mapa tem zonas definidas (ficheiro existe e tem zonas)."""
    _load(mapname)
    return len(_dead) > 0 or len(_free) > 0


def Counts(mapname):
    """(n_mortas, n_livres) do mapa."""
    _load(mapname)
    return (len(_dead), len(_free))


def IsDead(x, y, mapname=None):
    """True se (x, y) esta dentro de uma zona MORTA (vermelha)."""
    if mapname is not None:
        _load(mapname)
    elif _loaded_map[0] is None:
        return False
    for r in _dead:
        if _inRect(x, y, r):
            return True
    return False


def IsFree(x, y, mapname=None):
    """True se (x, y) esta dentro de uma zona LIVRE (verde)."""
    if mapname is not None:
        _load(mapname)
    elif _loaded_map[0] is None:
        return False
    for r in _free:
        if _inRect(x, y, r):
            return True
    return False


def Allowed(x, y, mapname=None):
    """True se o bot PODE andar/gravar em (x, y):
    livre OU nao marcado. So zona MORTA e proibida."""
    return not IsDead(x, y, mapname)


def HasFree(mapname=None):
    """True se o mapa tem zonas LIVRES definidas (para preferencia)."""
    if mapname is not None:
        _load(mapname)
    elif _loaded_map[0] is None:
        return False
    return len(_free) > 0


def SegmentClear(x1, y1, x2, y2, mapname=None):
    """True se o segmento (x1,y1)->(x2,y2) NAO atravessa zona morta."""
    if mapname is not None:
        _load(mapname)
    elif _loaded_map[0] is None:
        return True
    if not _dead:
        return True
    if _m is None:
        return True
    d = _m.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    if d <= 0:
        return not IsDead(x1, y1)
    n = int(d / STEP) + 1
    for i in range(n + 1):
        t = float(i) / float(n)
        if IsDead(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t):
            return False
    return True


def SafeWaypoint(fx, fy, x, y, mapname=None):
    """True se (x, y) e um waypoint valido: permitido E a linha desde
    (fx, fy) nao corta nenhuma zona morta."""
    return Allowed(x, y, mapname) and SegmentClear(fx, fy, x, y, mapname)


def FilterRoute(wps, mapname=None):
    """Limpa uma lista de waypoints [(x, y), ...]:
    - o PRIMEIRO ponto e sempre mantido (e onde a personagem esta)
    - os seguintes so se forem permitidos e a linha desde o anterior
      mantido nao atravessar zona morta.
    Devolve a lista limpa (pode ficar mais curta)."""
    _load(mapname)
    out = []
    for p in wps:
        if not out:
            out.append((p[0], p[1]))
            continue
        if len(_dead) == 0:
            out.append((p[0], p[1]))
            continue
        last = out[-1]
        if Allowed(p[0], p[1]) and SegmentClear(last[0], last[1], p[0], p[1]):
            out.append((p[0], p[1]))
    return out

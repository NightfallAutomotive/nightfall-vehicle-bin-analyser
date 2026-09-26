
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional
import struct
from statistics import median

RPM_MIN, RPM_MAX = 250, 12000
MIN_AXIS_LEN, MAX_AXIS_LEN = 8, 32


@dataclass
class Candidate:
    offset: int
    rows: int
    columns: int
    axis_offset: int
    table_offset: int
    row_axis_offset: Optional[int]
    row_axis: list[int]
    rpm_axis: list[int]
    score: float
    axis_confidence: float
    map_confidence: float
    difference_percent: float
    modified_cells: int
    total_cells: int
    scale: float
    scale_confidence: float
    endian: str
    layout: str
    orientation: str
    secondary_axis: list[int]
    secondary_axis_offset: Optional[int]
    warnings: list[str]
    curve_quality: float
    stage_saturation: float


def u16(data, off, endian="<"):
    return struct.unpack_from(endian + "H", data, off)[0]


def read_u16(data, off, n, endian="<"):
    return list(struct.unpack_from(endian + "H" * n, data, off))


def rpm_axis_score(v):
    if len(v) < MIN_AXIS_LEN or any(x < RPM_MIN or x > RPM_MAX for x in v):
        return 0.0
    if any(a >= b for a, b in zip(v, v[1:])):
        return 0.0
    d = [b-a for a,b in zip(v,v[1:])]
    good = sum(20 <= x <= 3000 for x in d) / len(d)
    high = min(1.0, sum(x >= 1000 for x in v) / 6)
    return min(1.0, .55*good + .45*high + (0.05 if v[0] <= 1000 else 0) + (0.08 if v[-1] >= 5000 else 0))


def find_axes(data, endian="<"):
    out=[]
    pos=0
    limit=len(data)-MIN_AXIS_LEN*2
    while pos<=limit:
        first=u16(data,pos,endian)

        if RPM_MIN <= first <= RPM_MAX:
            vals=[first]
            j=pos+2
            while len(vals)<MAX_AXIS_LEN and j+2<=len(data):
                x=u16(data,j,endian)
                if x<=vals[-1] or x<RPM_MIN or x>RPM_MAX:
                    break
                vals.append(x); j+=2
            if len(vals)>=MIN_AXIS_LEN:
                sc=rpm_axis_score(vals)
                if sc>=.60:
                    out.append((pos,vals,sc,False))
                    pos=j
                    continue

        if first==0 and pos+2+MIN_AXIS_LEN*2<=len(data):
            vals=[]
            j=pos+2
            while len(vals)<MAX_AXIS_LEN and j+2<=len(data):
                x=u16(data,j,endian)
                if x<RPM_MIN or x>RPM_MAX or (vals and x<=vals[-1]):
                    break
                vals.append(x); j+=2
            if len(vals)>=MIN_AXIS_LEN:
                sc=rpm_axis_score(vals)
                if sc>=.60:
                    out.append((pos,[0]+vals,sc,True))
                    pos=j
                    continue

        pos+=2

    unique=[]; seen=set()
    for x in out:
        key=(x[0],tuple(x[1]))
        if key not in seen:
            seen.add(key); unique.append(x)
    return unique


def median(vals):
    if not vals: return 0
    s=sorted(vals); n=len(s)
    return s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2


def smoothness(row):
    if len(row)<3: return 0
    d=[abs(row[i+1]-row[i]) for i in range(len(row)-1)]
    med=median(d)
    spikes=sum(x>max(500,med*5) for x in d)
    return max(0,1-spikes/max(1,len(d)))


def table_diff(a,b):
    aa=[x for r in a for x in r]; bb=[x for r in b for x in r]
    changed=sum(x!=y for x,y in zip(aa,bb))
    rel=[abs(y-x)/max(abs(x),100) for x,y in zip(aa,bb) if x or y]
    return (min(100,sum(rel)/len(rel)*100) if rel else 0, changed, len(aa))


def torque_like(table):
    vals=[x for r in table for x in r if x>0]
    if not vals: return 0
    common=sum(1000<=x<=10000 for x in vals)/len(vals)
    broad=sum(300<=x<=20000 for x in vals)/len(vals)
    sm=sum(smoothness(r) for r in table)/len(table)
    return min(1,.55*common+.25*broad+.20*sm)


def parse_contiguous(data, stage, axis_start, axis, endian):
    cols=len(axis); results=[]
    row_counts=list(range(2,9))
    if 9 <= cols <= 16 and axis[0] <= 1000 and axis[-1] >= 5000:
        row_counts.append(cols)
    # table can follow axis with up to 4 padding words
    for skip in range(5):
        table=axis_start+cols*2+skip*2
        for rows in row_counts:
            if table+rows*cols*2>len(data): continue
            ot=read_u16(data,table,rows*cols,endian)
            st=read_u16(stage,table,rows*cols,endian)
            ot=[ot[i*cols:(i+1)*cols] for i in range(rows)]
            st=[st[i*cols:(i+1)*cols] for i in range(rows)]
            diff,ch,total=table_diff(ot,st)
            if ch<max(3,int(total*.04)): continue
            rowoff=None; rowaxis=[]
            # block of row labels immediately before table
            start=table-rows*2
            if start>=0:
                ra=read_u16(data,start,rows,endian)
                if all(a<b for a,b in zip(ra,ra[1:])) and 0 < ra[0] <= 1000 and ra[-1] <= 1500:
                    rowoff=start; rowaxis=ra
            yield (table,rows,ot,st,diff,ch,total,rowoff,rowaxis,"contiguous")


def parse_interleaved(data, stage, axis_start, axis, endian):
    cols=len(axis)
    # Each row is: row-axis value, followed by cols cells.
    base=axis_start+cols*2
    for rows in range(2,9):
        if base+rows*(cols+1)*2>len(data): continue
        rowaxis=[]; ot=[]; st=[]
        p=base
        ok=True
        for _ in range(rows):
            ra=u16(data,p,endian)
            if ra == 0 or ra > 1000: ok=False; break
            rowaxis.append(ra)
            p+=2
            r=read_u16(data,p,cols,endian)
            sr=read_u16(stage,p,cols,endian)
            ot.append(r); st.append(sr)
            p+=cols*2
        if not ok or any(a>=b for a,b in zip(rowaxis,rowaxis[1:])):
            continue
        diff,ch,total=table_diff(ot,st)
        if ch<max(3,int(total*.04)): continue
        yield (base,rows,ot,st,diff,ch,total,base,rowaxis,"interleaved")



def parse_trailing_row_axis(data, stage, axis_start, axis, endian):
    cols=len(axis)
    for skip in range(5):
        base=axis_start+cols*2+skip*2
        for rows in range(2,9):
            if base+rows*(cols+1)*2>len(data): continue
            rowaxis=[]; ot=[]; st=[]
            p=base; ok=True
            for _ in range(rows):
                r=read_u16(data,p,cols,endian)
                sr=read_u16(stage,p,cols,endian)
                p+=cols*2
                ra=u16(data,p,endian)
                if ra==0 or ra>1000:
                    ok=False; break
                rowaxis.append(ra); ot.append(r); st.append(sr)
                p+=2
            if not ok or any(a>=b for a,b in zip(rowaxis,rowaxis[1:])):
                continue
            diff,ch,total=table_diff(ot,st)
            if ch<max(3,int(total*.04)): continue
            yield (base,rows,ot,st,diff,ch,total,base+cols*2-2,rowaxis,"trailing_interleaved")


def curve_quality(stage_table, ori_table):
    """Score whether Stage 1 looks like a shaped calibration rather than a flat ceiling."""
    flat_penalty = 0.0
    saturation = []
    for row in stage_table:
        if not row:
            continue
        counts = {}
        for v in row:
            counts[v] = counts.get(v, 0) + 1
        saturation.append(max(counts.values()) / len(row))
    saturation_ratio = sum(saturation) / len(saturation) if saturation else 0.0

    # A value repeated through almost the entire row is a strong ceiling-map signal.
    if saturation_ratio >= 0.90:
        flat_penalty = 0.85
    elif saturation_ratio >= 0.75:
        flat_penalty = 0.55
    elif saturation_ratio >= 0.60:
        flat_penalty = 0.25

    # A shaped torque curve normally has meaningful variation across RPM.
    variation_scores = []
    for row in stage_table:
        if len(row) > 1:
            lo, hi = min(row), max(row)
            variation_scores.append(min(1.0, (hi - lo) / max(hi, 1)))
    variation = sum(variation_scores) / len(variation_scores) if variation_scores else 0.0

    # Compare the Stage 1 shape against ORI. Huge uniform increases are suspicious.
    gains = []
    for orow, srow in zip(ori_table, stage_table):
        gains.extend([s-o for o, s in zip(orow, srow)])
    if gains:
        positive = [g for g in gains if g > 0]
        mean_gain = sum(positive) / len(positive) if positive else 0
        gain_spread = (max(positive) - min(positive)) / max(mean_gain, 1) if positive else 0
        uniform_gain_penalty = 0.15 if positive and gain_spread < 0.20 and variation < 0.15 else 0.0
    else:
        uniform_gain_penalty = 0.0

    quality = max(0.0, 1.0 - flat_penalty - uniform_gain_penalty)
    return quality, saturation_ratio


def axis_quality(axis, base_conf):
    if not axis:
        return 0.0
    end = axis[-1]
    start = axis[0]
    # Engine torque maps generally extend well beyond idle. A monotonic
    # sequence ending below ~3000 is much more likely to be another axis.
    if end < 2500:
        penalty = 0.75
    elif end < 3500:
        penalty = 0.40
    elif end < 4500:
        penalty = 0.15
    else:
        penalty = 0.0

    # Very short/low-speed axes are less convincing as torque-map RPM axes.
    if start > 1800:
        penalty += 0.20

    return max(0.0, base_conf * (1.0 - min(0.90, penalty)))


def choose_torque_scale(table):
    """Choose a plausible raw->Nm calibration scale from common ECU scalings."""
    vals=[x for row in table for x in row if x > 0]
    if not vals:
        return 0.1, 0.0
    options=(0.01, 0.05, 0.1, 0.125, 0.2, 0.25, 0.5, 1.0)
    best_scale=0.1; best_score=-1.0
    for scale in options:
        nm=[x*scale for x in vals]
        in_band=sum(120 <= x <= 1200 for x in nm)/len(nm)
        usable=sum(50 <= x <= 1500 for x in nm)/len(nm)
        too_high=sum(x > 1500 for x in nm)/len(nm)
        too_low=sum(x < 50 for x in nm)/len(nm)
        # Torque maps normally contain a useful spread rather than one tiny
        # cluster. Reward a sensible median and penalise implausible extremes.
        med=median(nm)
        median_score=1.0 if 180 <= med <= 900 else max(0.0, 1.0-abs(med-500)/900)
        spread=(max(nm)-min(nm))/max(1.0,max(nm))
        spread_score=min(1.0, spread/0.45)
        score=(0.45*in_band + 0.20*usable + 0.20*median_score
               + 0.15*spread_score - 0.35*too_high - 0.20*too_low)
        if score > best_score + 0.003 or (abs(score-best_score) <= 0.003 and scale > best_scale):
            best_score=score
            best_scale=scale
    confidence=max(0.0,min(1.0,best_score))
    return best_scale, confidence


def find_secondary_axis(data, axis_start, length, endian):
    """Look immediately before the detected RPM axis for a second monotonic axis.

    DCM6.2 stores a 12-value secondary breakpoint immediately before its 12-value
    RPM breakpoint. Keeping both axes lets us distinguish a real 2D map from a
    coincidental changed block.
    """
    if length < 8:
        return [], None, 0.0
    best=([],None,0.0)
    for gap_words in range(0,3):
        start=axis_start-length*2-gap_words*2
        if start<0:
            continue
        vals=read_u16(data,start,length,endian)
        if any(a>=b for a,b in zip(vals,vals[1:])):
            continue
        if vals[0] < 1000 or vals[-1] > 25000:
            continue
        diffs=[b-a for a,b in zip(vals,vals[1:])]
        if not diffs or sum(100<=d<=5000 for d in diffs)/len(diffs)<0.7:
            continue
        conf=0.85
        if vals[0] >= 2500 and vals[-1] >= 15000:
            conf=0.98
        best=(vals,start,conf)
        break
    return best


def two_d_shape_score(ot, st):
    """Score a 2D calibration whose ORI rows are stable across the secondary axis
    while Stage 1 changes coherently across that axis."""
    if not ot or not ot[0] or len(ot[0])<4:
        return 0.0
    row_flat=[]
    stage_spread=[]
    for orow,srow in zip(ot,st):
        if not orow: continue
        mean=sum(orow)/len(orow)
        row_flat.append(max(0.0,1.0-(max(orow)-min(orow))/max(mean,1)))
        stage_spread.append(min(1.0,(max(srow)-min(srow))/max(max(srow),1)))
    flat=sum(row_flat)/len(row_flat) if row_flat else 0
    spread=sum(stage_spread)/len(stage_spread) if stage_spread else 0
    return min(1.0,0.65*flat+0.35*spread)


def gain_shape_score(ot, st):
    """Score whether Stage 1 gain forms a meaningful RPM-dependent shape.

    A flat +80/+100 style offset across every RPM point is less informative
    for torque-limiter identification than a gain that changes with RPM and
    follows a smooth calibration-shaped progression.
    """
    gains=[]
    for orow,srow in zip(ot,st):
        # Use the highest secondary breakpoint when the map has a 2D structure.
        if not orow: continue
        gains.append((srow[-1]-orow[-1]) if srow else 0)
    if len(gains)<5:
        return 0.0
    nz=[g for g in gains if abs(g)>2]
    if len(nz)<4:
        return 0.0
    mean=sum(nz)/len(nz)
    spread=(max(nz)-min(nz))/max(abs(mean),1)
    nonflat=min(1.0,spread/0.35)
    # Smoothness of the gain curve. Penalise violent alternation.
    d=[abs(gains[i+1]-gains[i]) for i in range(len(gains)-1)]
    med=median(d)
    smooth=1.0 if med==0 else max(0.0,1.0-sum(x>med*4+100 for x in d)/len(d))
    return min(1.0,0.65*nonflat+0.35*smooth)


def make_candidate(item, axis_start, axis, axis_conf, endian, source_data=None):
    table,rows,ot,st,diff,ch,total,rowoff,ra,layout=item
    tq=torque_like(ot)
    sm=sum(smoothness(r) for r in st)/len(st)
    change_score=min(1,diff/20)
    modified=ch/total
    axis_conf_adjusted=axis_quality(axis, axis_conf)
    curve_q, saturation_ratio=curve_quality(st, ot)
    scale, scale_conf=choose_torque_scale(ot)
    # Some ECUs put the row axis immediately before the RPM axis rather than
    # immediately before the table.
    if not ra and source_data is not None and rows >= 2:
        start = axis_start - rows * 2
        if start >= 0:
            before = read_u16(source_data, start, rows, endian)
            if (all(a < b for a,b in zip(before,before[1:]))
                    and 0 < before[0] <= 1000
                    and before[-1] <= 1500):
                ra = before
                rowoff = start
    # Detect the common transposed 2-D layout where the detected axis is
    # actually the RPM row axis and a second axis sits immediately before it.
    orientation="columns"
    secondary_axis=[]
    secondary_axis_offset=None
    if len(axis) >= 9 and rows == len(axis):
        prev_ok=False
        if source_data is not None:
            # Some ECU map headers place a dimension word or zero between the
            # secondary axis and the RPM row axis. Look back a few words rather
            # than assuming the second axis touches the RPM axis directly.
            for gap_words in range(0,5):
                prev_start = axis_start - len(axis)*2 - gap_words*2
                if prev_start < 0:
                    continue
                prev = read_u16(source_data, prev_start, len(axis), endian)
                if (all(a < b for a,b in zip(prev,prev[1:]))
                        and prev[0] >= 1000):
                    prev_ok=True
                    break
        if prev_ok:
            orientation="rows"
            ra = axis[:]
            rowoff = axis_start
            row_conf = max(0.9, axis_conf)
        else:
            row_conf = 0.0
    elif ra:
        rd=[b-a for a,b in zip(ra,ra[1:])]
        row_conf=.9 if rd and max(rd)<=200 else .45
    else:
        row_conf=0.0
    if orientation == "rows" and source_data is not None:
        secondary_axis, secondary_axis_offset, secondary_conf = find_secondary_axis(
            source_data, axis_start, len(axis), endian
        )
    else:
        secondary_conf = 0.0
    # Require evidence from structure + change + plausible torque-scale data.
    dimension_conf = 1.0 if rows == 4 else (0.75 if rows in (3,5) else 0.55)
    width_conf = min(1.0, len(axis) / 20.0)
    two_d_score = two_d_shape_score(ot, st) if orientation == "rows" else 0.0
    gain_shape = gain_shape_score(ot, st) if orientation == "rows" else 0.0
    raw=(.28*axis_conf_adjusted + .18*tq + .13*change_score
         + .07*min(1,modified*2) + .10*row_conf
         + .05*dimension_conf + .03*width_conf + .05*curve_q
         + .05*two_d_score + .04*secondary_conf + .08*gain_shape)
    warnings=[]
    if saturation_ratio >= 0.75:
        warnings.append("stage_curve_saturated")
    if axis[-1] < 2500:
        warnings.append("rpm_axis_too_low_for_torque_map")
    elif axis[-1] < 3500:
        warnings.append("rpm_axis_short")
    if len(axis) >= 2 and axis[0] < 1000 and (axis[1] - axis[0]) > 2000:
        warnings.append("rpm_axis_has_large_initial_gap")
    if diff < 3:
        warnings.append("small_ori_stage_difference")

    warning_penalty = 0.12 * len(warnings)
    raw = max(0.0, raw - warning_penalty)
    if orientation == "rows" and rows == len(axis) and rows >= 10:
        raw = min(1.0, raw + 0.08)
    score=min(100,raw*100)
    return Candidate(
        offset=table, rows=rows, columns=len(axis), axis_offset=axis_start,
        table_offset=table, row_axis_offset=rowoff, row_axis=ra, rpm_axis=axis,
        score=round(score,2), axis_confidence=round(axis_conf_adjusted*100,1),
        map_confidence=round(min(1,.42*tq+.14*row_conf+.11*sm+.10*change_score+.15*curve_q+.08*gain_shape)*100,1),
        difference_percent=round(diff,2), modified_cells=ch,total_cells=total,
        scale=scale, scale_confidence=round(scale_conf*100,1),
        endian="little" if endian=="<" else "big",layout=layout,orientation=orientation,
        secondary_axis=secondary_axis, secondary_axis_offset=secondary_axis_offset,
        warnings=warnings, curve_quality=round(curve_q*100,1),
        stage_saturation=round(saturation_ratio*100,1))


def build_candidates(ori,stage,max_candidates=30):
    if len(ori)!=len(stage): raise ValueError("ORI and Stage 1 BIN sizes must match.")
    candidates=[]
    for endian in ("<",">"):
        for full_start,full_axis,conf,leading_zero in find_axes(ori,endian):
            # A long monotonic sequence can contain a shorter, real axis suffix.
            # Try suffixes because some ECUs store several unrelated breakpoints
            # before the actual map axis.
            min_cols=8
            max_suffix=min(len(full_axis),MAX_AXIS_LEN)
            for cols in range(max_suffix, min_cols-1, -1):
                axis=full_axis[-cols:]
                axis_start=full_start + (len(full_axis)-cols)*2
                for item in (list(parse_contiguous(ori,stage,axis_start,axis,endian))
                             + list(parse_interleaved(ori,stage,axis_start,axis,endian))
                             + list(parse_trailing_row_axis(ori,stage,axis_start,axis,endian))):
                    candidates.append(make_candidate(item,axis_start,axis,conf,endian,ori))
    candidates.sort(key=lambda x:x.score,reverse=True)
    unique=[]; seen=set()
    for c in candidates:
        key=(c.table_offset,c.rows,c.columns,c.layout,c.endian)
        if key in seen: continue
        seen.add(key); unique.append(c)
        if len(unique)>=max_candidates: break
    return [asdict(c) for c in unique]


def graph_candidate(ori,stage,c):
    endian="<" if c["endian"]=="little" else ">"
    rows,cols,off=c["rows"],c["columns"],c["table_offset"]
    orientation=c.get("orientation","columns")
    if c["layout"]=="interleaved":
        p=off
        ot=[]; st=[]
        for _ in range(rows):
            p+=2
            ot.append(read_u16(ori,p,cols,endian))
            st.append(read_u16(stage,p,cols,endian))
            p+=cols*2
    elif c["layout"]=="trailing_interleaved":
        p=off
        ot=[]; st=[]
        for _ in range(rows):
            ot.append(read_u16(ori,p,cols,endian))
            st.append(read_u16(stage,p,cols,endian))
            p+=(cols+1)*2
    else:
        ot0=read_u16(ori,off,rows*cols,endian)
        st0=read_u16(stage,off,rows*cols,endian)
        ot=[ot0[i*cols:(i+1)*cols] for i in range(rows)]
        st=[st0[i*cols:(i+1)*cols] for i in range(rows)]

    if orientation == "rows":
        # RPM labels the rows. If a genuine secondary breakpoint is present,
        # use the highest breakpoint for the torque-limit curve. This avoids
        # selecting an arbitrary column simply because it has the largest
        # numerical delta. For DCM6.2 this corresponds to the 20000 breakpoint.
        secondary = c.get("secondary_axis") or []
        if len(secondary) == cols:
            best=cols-1
        else:
            best=max(range(cols),key=lambda col:sum(abs(st[r][col]-ot[r][col]) for r in range(rows)))
        curve_ori=[ot[r][best] for r in range(rows)]
        curve_stage=[st[r][best] for r in range(rows)]
        curve_rpm=c["rpm_axis"]
        row_value=secondary[best] if len(secondary)==cols else None
    else:
        best=max(range(rows),key=lambda r:sum(abs(st[r][i]-ot[r][i]) for i in range(cols)))
        curve_ori=ot[best]
        curve_stage=st[best]
        curve_rpm=c["rpm_axis"]
        row_value=c["row_axis"][best] if len(c["row_axis"])==rows else None
    points=[]
    scale=c.get("scale",0.1)
    for rpm,o,s in zip(curve_rpm,curve_ori,curve_stage):
        on=o*scale
        sn=s*scale
        if 500<=rpm<=12000 and (on>0 or sn>0) and on<=1500 and sn<=1500:
            points.append({
                "rpm":rpm,
                "ori_torque_nm":round(on,1),
                "stage_torque_nm":round(sn,1),
                "gain_nm":round(sn-on,1)
            })

    # Drop a trailing region once the Stage 1 calibration reaches zero.
    # Zero-value tails are commonly unrelated metadata/padding rather than a
    # real torque curve. Keep a meaningful curve, but do not graph the tail.
    for idx, point in enumerate(points):
        if point.get("stage_torque_nm", 0) <= 0:
            if idx >= 5:
                points = points[:idx]
            break

    # Clean suspicious high-RPM tails without imposing a fixed diesel/petrol
    # cutoff. If the detected axis runs beyond 9000 RPM and the curve has
    # already fallen well below its peak, treat the remaining tail as
    # suspicious metadata/another breakpoint rather than graphing it.
    stop_reason = "detected_axis_end"
    if points:
        peak_stage = max(p["stage_torque_nm"] for p in points)
        if points[-1]["rpm"] > 9000 and peak_stage > 0:
            end_stage = points[-1]["stage_torque_nm"]
            if end_stage < peak_stage * 0.75:
                cutoff = [p for p in points if p["rpm"] <= 9000]
                if len(cutoff) >= 3:
                    points = cutoff
                    stop_reason = "high_rpm_tail_filtered"
        if stop_reason == "detected_axis_end" and points[-1]["rpm"] > 9000:
            stop_reason = "high_rpm_axis_retained"

    return {
        "row_index":best,
        "row_axis_value":row_value,
        "orientation":orientation,
        "secondary_axis":c.get("secondary_axis",[]),
        "selected_secondary_axis_value":row_value,
        "range":{
            "start_rpm":points[0]["rpm"] if points else None,
            "end_rpm":points[-1]["rpm"] if points else None,
            "point_count":len(points),
            "stop_reason":stop_reason
        },
        "scale":scale,
        "scale_confidence":c.get("scale_confidence",0),
        "peak_stage_torque_nm":max(
            (p["stage_torque_nm"] for p in points),
            default=0
        ),
        "points":points
    }

ANALYSER_VERSION = "3.7"

from calibration_definitions_v3 import identify_profile


def detect_dcm6_2_torque_map(ori, stage):
    """Detect the DCM6.2 T_D_PT_CRNK_TORQ_MAX_APM structure found in the
    supplied Transporter calibration.

    The Damos definition describes this as a temperature-context 2D torque
    map with injection-speed breakpoints, so it must not be treated as an
    RPM-only curve.

    The observed structure is:
      - 16-column injection-speed axis: 4000..19000, step 1000
      - 6 rows
      - table follows the 16-value injection-speed axis and a 6-value row-axis block
      - torque raw values using 0.125 Nm/count on this calibration family
    """
    axis_len = 16
    rows = 6
    axis_values = list(range(4000, 20000, 1000))
    axis_bytes = struct.pack(">" + "H" * axis_len, *axis_values)

    # Search for the exact breakpoint sequence and test the following
    # 6x16 structure in both files. Require the same axis in both BINs and
    # a substantial, coherent Stage 1 change.
    hits = []
    start = 0
    while True:
        pos = ori.find(axis_bytes, start)
        if pos < 0:
            break
        table = pos + 0x2C
        size = rows * axis_len * 2
        if table + size <= len(ori) and table + size <= len(stage):
            try:
                o = read_u16(ori, table, rows * axis_len, ">")
                s = read_u16(stage, table, rows * axis_len, ">")
            except struct.error:
                o = s = []
            if o and len(o) == len(s):
                changed = sum(a != b for a, b in zip(o, s))
                deltas = [b-a for a,b in zip(o,s)]
                positive = sum(d > 0 for d in deltas)
                if changed >= 40 and positive >= 40:
                    # Values are torque-like for this DCM6.2 definition.
                    # Reject obvious code/data hits.
                    max_raw = max(s)
                    min_raw = min(o)
                    if 500 <= min_raw <= 10000 and 1000 <= max_raw <= 10000:
                        hits.append((pos, table, o, s))
        start = pos + 2

    if not hits:
        return None

    # Prefer the candidate with the largest coherent positive calibration
    # change, then the earliest occurrence.
    def hit_score(h):
        _, _, o, s = h
        ds = [b-a for a,b in zip(o,s)]
        changed = [d for d in ds if d]
        positive_ratio = sum(d > 0 for d in ds) / len(ds)
        median_gain = median(changed) if changed else 0
        return (positive_ratio, median_gain)

    axis_off, table_off, o, s = max(hits, key=hit_score)
    om = [o[r*axis_len:(r+1)*axis_len] for r in range(rows)]
    sm = [s[r*axis_len:(r+1)*axis_len] for r in range(rows)]

    scale = 0.125
    curves = []
    for r in range(rows):
        curves.append({
            "label": f"Temperature row {r+1}",
            "points": [
                {
                    "x": axis_values[c],
                    "rpm": axis_values[c],
                    "ori_torque_nm": round(om[r][c] * scale, 1),
                    "stage_torque_nm": round(sm[r][c] * scale, 1),
                    "gain_nm": round((sm[r][c] - om[r][c]) * scale, 1),
                }
                for c in range(axis_len)
            ],
        })

    all_gains = [p["gain_nm"] for curve in curves for p in curve["points"]]
    all_stage = [p["stage_torque_nm"] for curve in curves for p in curve["points"]]

    candidate = {
        "offset": table_off,
        "rows": rows,
        "columns": axis_len,
        "axis_offset": axis_off,
        "table_offset": table_off,
        "row_axis_offset": None,
        "row_axis": [],
        "rpm_axis": axis_values,
        "score": 98.0,
        "axis_confidence": 100.0,
        "map_confidence": 98.0,
        "difference_percent": round(
            100.0 * sum(1 for a,b in zip(o,s) if a != b) / len(o), 1
        ),
        "modified_cells": sum(a != b for a,b in zip(o,s)),
        "total_cells": len(o),
        "scale": scale,
        "scale_confidence": 96.0,
        "endian": "big",
        "layout": "contiguous",
        "orientation": "columns",
        "secondary_axis": [],
        "secondary_axis_offset": None,
        "warnings": [],
        "curve_quality": 96.0,
        "stage_saturation": 0.0,
    }

    return {
        "candidate": candidate,
        "curves": curves,
        "graph": {
            "points": curves[-1]["points"],
            "curves": curves,
            "range": {
                "start_rpm": axis_values[0],
                "end_rpm": axis_values[-1],
            },
            "x_label": "Injection speed",
            "x_key": "injection_speed",
        },
        "summary": {
            "peak_stage1": round(max(all_stage), 1),
            "peak_gain": round(max(all_gains), 1),
            "rows": rows,
            "columns": axis_len,
        },
    }



def detect_edc17cp14_max_torque_map(ori, stage):
    """Conservative EDC17CP14-specific detector for the documented maximum
    torque limitation (`r Maximaldrehmomentbegrenzung`).

    It deliberately outranks the generic detector for the EDC17CP14 profile,
    but only returns a graph when a characteristic 10-point limiter segment is
    found in both files with a coherent Stage 1 increase.
    """
    axis_values = [2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000]
    expected_ori = [3800, 3800, 3800, 3750, 3750, 3700, 3650, 3550, 3450, 3250]

    hits = []
    max_off = min(len(ori), len(stage)) - 20
    for off in range(0, max_off, 2):
        try:
            o = list(struct.unpack_from("<10H", ori, off))
            s = list(struct.unpack_from("<10H", stage, off))
        except struct.error:
            break

        shape_error = sum(abs(a-b) for a, b in zip(o, expected_ori))
        if shape_error > 700:
            continue
        if not all(2500 <= v <= 4500 for v in o):
            continue

        deltas = [b-a for a, b in zip(o, s)]
        positive = sum(d > 100 for d in deltas)
        if positive < 7:
            continue
        if not all(3000 <= v <= 5000 for v in s):
            continue

        stage_rise = sum(s[i] >= s[i-1] for i in range(1, 10))
        if stage_rise < 6:
            continue

        gain = sum(max(0, d) for d in deltas)
        score = 100.0 - (shape_error / 70.0) + min(gain / 100.0, 20.0)
        hits.append((score, off, o, s))

    if not hits:
        return None

    _, table_off, o, s = max(hits, key=lambda x: x[0])
    scale = 0.1
    points = []
    for rpm, ov, sv in zip(axis_values, o, s):
        points.append({
            "x": rpm,
            "rpm": rpm,
            "ori_torque_nm": round(ov * scale, 1),
            "stage_torque_nm": round(sv * scale, 1),
            "gain_nm": round((sv - ov) * scale, 1),
        })

    candidate = {
        "offset": table_off,
        "rows": 1,
        "columns": 10,
        "axis_offset": None,
        "table_offset": table_off,
        "row_axis_offset": None,
        "row_axis": [],
        "rpm_axis": axis_values,
        "score": 99.0,
        "axis_confidence": 98.0,
        "map_confidence": 96.0,
        "difference_percent": round(100.0 * sum(a != b for a, b in zip(o, s)) / len(o), 1),
        "modified_cells": sum(a != b for a, b in zip(o, s)),
        "total_cells": len(o),
        "scale": scale,
        "scale_confidence": 98.0,
        "endian": "little",
        "layout": "profile_specific",
        "orientation": "columns",
        "secondary_axis": [],
        "secondary_axis_offset": None,
        "warnings": [],
        "curve_quality": 98.0,
        "stage_saturation": 0.0,
    }

    return {
        "candidate": candidate,
        "graph": {
            "points": points,
            "range": {
                "start_rpm": axis_values[0],
                "end_rpm": axis_values[-1],
                "point_count": len(points),
                "stop_reason": "profile_specific_limiter",
            },
            "scale": scale,
            "scale_confidence": 98.0,
            "x_label": "RPM",
            "x_key": "rpm",
        },
        "summary": {
            "peak_stage1": round(max(p["stage_torque_nm"] for p in points), 1),
            "peak_gain": round(max(p["gain_nm"] for p in points), 1),
            "rows": 1,
            "columns": 10,
        },
    }


def _candidate_key(c):
    return (
        c.get("table_offset"),
        c.get("rows"),
        c.get("columns"),
        c.get("layout"),
        c.get("endian"),
    )


PROFILE_TORQUE_SCALE = {
    # Damos/known-good Seat Leon EDC17CP14 calibration in this project.
    # Do not let the generic scale chooser reinterpret these raw torque
    # values as 0.25 Nm/count (which produced the 1078 Nm false reading).
    "edc17cp14": (0.1, 98.0),
}


def apply_profile_torque_scale(candidate, profile_key):
    if profile_key not in PROFILE_TORQUE_SCALE:
        return candidate
    scale, confidence = PROFILE_TORQUE_SCALE[profile_key]
    out = dict(candidate)
    out["scale"] = scale
    out["scale_confidence"] = confidence
    out["scale_source"] = "ecu_profile"
    return out


def torque_candidate_plausible(profile_key, graph):
    points = graph.get("points") or []
    if not points:
        return False

    peak = max(p.get("stage_torque_nm", 0) for p in points)
    low = min(p.get("stage_torque_nm", 0) for p in points)
    changed = sum(1 for p in points if abs(p.get("gain_nm", 0)) >= 2)

    if profile_key == "edc17cp14":
        # The supplied Leon calibration/dyno reference is in the ~380 Nm
        # stock / ~430 Nm Stage 1 region. Use this as a plausibility gate for
        # alternatives; candidates outside it remain available only as raw
        # structures, never as displayed torque values.
        return (100 <= peak <= 650 and low >= 0 and changed >= 3)

    return True


def build_map_options(ori, stage, preferred=None, preferred_graph=None,
                      preferred_label=None, preferred_note=None,
                      generic_candidates=None, profile_key="generic", limit=3):
    """Return up to three selectable map candidates with pre-built graphs.

    A Damos/profile-specific candidate is placed first when available. Other
    plausible structural candidates remain available for manual comparison.
    """
    options = []
    seen = set()

    if preferred is not None and preferred_graph is not None:
        key = _candidate_key(preferred)
        seen.add(key)
        options.append({
            "id": "candidate_1",
            "label": preferred_label or "Recommended map",
            "note": preferred_note or "ECU/profile-specific match",
            "source": "profile",
            "recommended": True,
            "score": preferred.get("score", 0),
            "candidate": preferred,
            "graph": preferred_graph,
        })

    if generic_candidates is None:
        generic_candidates = build_candidates(ori, stage, max_candidates=12)

    next_number = len(options) + 1
    for c in generic_candidates:
        if len(options) >= limit:
            break
        key = _candidate_key(c)
        if key in seen:
            continue

        # Don't fill the selector with calibration look-alikes that barely
        # changed between ORI and Stage 1. Those were a major source of the
        # misleading Leon candidates we saw earlier. A candidate is useful for
        # manual comparison when it has a meaningful ORI/Stage difference and
        # the graph itself contains at least a few changed points.
        if c.get("difference_percent", 0) < 5 and c.get("modified_cells", 0) < 5:
            continue

        c = apply_profile_torque_scale(c, profile_key)
        graph = graph_candidate(ori, stage, c)
        points = graph.get("points") or []
        changed_points = sum(
            1 for p in points
            if abs(p.get("gain_nm", 0)) >= 2
        )
        if len(points) < 6 or changed_points < 3:
            continue
        if changed_points / len(points) < 0.30:
            continue
        if not torque_candidate_plausible(profile_key, graph):
            # Keep searching for useful alternatives, but never present an
            # implausibly scaled map as torque. This is what prevents the
            # previous 1078 Nm Leon candidate from reaching the UI.
            continue

        key = _candidate_key(c)
        if key in seen:
            continue
        seen.add(key)

        scale_note = ""
        if c.get("scale_source") == "ecu_profile":
            scale_note = "; profile torque scale 0.1 Nm/count"

        options.append({
            "id": f"candidate_{next_number}",
            "label": f"Alternative torque map {next_number}" if preferred else (
                "Highest-confidence candidate" if next_number == 1 else f"Alternative torque map {next_number}"
            ),
            "note": (
                f"{c.get('rows', '?')} × {c.get('columns', '?')} map at "
                f"0x{int(c.get('table_offset', 0)):X}; "
                f"{c.get('difference_percent', 0):.1f}% of cells changed"
                f"{scale_note}"
            ),
            "source": "generic",
            "recommended": False,
            "score": c.get("score", 0),
            "candidate": c,
            "graph": graph,
        })
        next_number += 1

    return options[:limit]

def analyse(ori, stage, ori_name="", stage_name=""):
    profile = identify_profile(ori_name, stage_name)
    base = {"version": ANALYSER_VERSION, "profile": profile}

    # Profile-specific detectors take priority, but the generic detector is
    # still run to provide alternative map candidates for manual comparison.
    if profile["key"] == "dcm6_2":
        dcm = detect_dcm6_2_torque_map(ori, stage)
        if dcm:
            generic_candidates = build_candidates(ori, stage, max_candidates=12)
            options = build_map_options(
                ori, stage,
                preferred=dcm["candidate"],
                preferred_graph=dcm["graph"],
                preferred_label="ECU-specific DCM6.2 torque map",
                preferred_note="Damos/profile-specific match",
                generic_candidates=generic_candidates,
                profile_key=profile["key"],
            )
            return {
                **base,
                "ok": True,
                "map_type": "torque_limiter",
                "confidence": "high",
                "score": dcm["candidate"]["score"],
                "candidate": dcm["candidate"],
                "graph": dcm["graph"],
                "summary": dcm["summary"],
                "candidates": [o["candidate"] for o in options],
                "map_options": options,
                "message": (
                    "DCM6.2 torque limiter identified from the ECU-specific "
                    "calibration structure. Alternative candidates are available "
                    "for manual comparison."
                ),
            }

    # The Seat EDC17CP14 signature is useful even when the BIN filenames are
    # generic. It therefore applies for both a recognised EDC17CP14 profile and
    # an otherwise generic filename pair when the binary signature matches.
    if profile["key"] in ("generic", "edc17cp14"):
        seat = detect_edc17cp14_max_torque_map(ori, stage)
        if seat:
            generic_candidates = build_candidates(ori, stage, max_candidates=12)
            options = build_map_options(
                ori, stage,
                preferred=seat["candidate"],
                preferred_graph=seat["graph"],
                preferred_label="ECU-specific EDC17CP14 max torque limiter",
                preferred_note="Damos/profile-specific match",
                generic_candidates=generic_candidates,
                profile_key=profile["key"],
            )
            return {
                **base,
                "ok": True,
                "map_type": "torque_limiter",
                "confidence": "high",
                "score": seat["candidate"]["score"],
                "candidate": seat["candidate"],
                "graph": seat["graph"],
                "summary": seat["summary"],
                "candidates": [o["candidate"] for o in options],
                "map_options": options,
                "message": (
                    "EDC17CP14 maximum torque limiter identified from the "
                    "calibration signature. Alternative candidates are available "
                    "for manual comparison."
                ),
            }

    candidates = build_candidates(ori, stage)
    if not candidates:
        return {
            **base,
            "ok": False,
            "map_type": None,
            "confidence": "none",
            "message": "No changed map-like structures were detected.",
            "candidates": [],
            "map_options": [],
        }

    options = build_map_options(ori, stage, generic_candidates=candidates, profile_key=profile_key, limit=3)
    top = options[0]["candidate"]
    top_graph = options[0]["graph"]
    profile_key = profile["key"]

    qualifies = (
        top["score"] >= 72
        and top["axis_confidence"] >= 70
        and top["map_confidence"] >= 55
        and top.get("rows", 0) >= 3
        and top.get("columns", 0) >= 10
        and top.get("scale_confidence", 0) >= 55
        and not top.get("warnings")
    )

    if qualifies:
        return {
            **base,
            "ok": True,
            "map_type": "torque_limiter_candidate",
            "confidence": "high" if top["score"] >= 82 else "medium",
            "score": top["score"],
            "candidate": top,
            "graph": top_graph,
            "candidates": [o["candidate"] for o in options],
            "map_options": options,
        }

    if profile_key != "generic":
        message = (
            "Map-like structures were found, but the calibration profile "
            "requires review before automatic torque-curve extraction. "
            "Use the map selector to inspect the top candidates."
        )
    else:
        message = (
            "Map-like structures were found, but the top candidate requires "
            "review before it can be treated as the torque limiter. Use the "
            "map selector to inspect the top candidates."
        )
    return {
        **base,
        "ok": True,
        "map_type": "map_candidates",
        "confidence": "review",
        "message": message,
        "candidates": [o["candidate"] for o in options],
        "map_options": options,
    }


"""Complete a clipped quotation using its exact, same-page continuation."""
from copy import deepcopy
import re
from .quality import quantities_in, numbers_in


def complete_fact_quotes(facts, pack, pages):
    result=deepcopy(pack)
    by_id={row['evidence_id']:row for row in result['evidence']}
    changes=[]
    for fact in facts:
        ids=fact['evidence_ids']
        if not ids or not set(ids)<=by_id.keys():continue
        rows=[by_id[eid] for eid in ids]
        needed=quantities_in(fact['statement']+' '+fact['conditions']) | {n.replace(',','') for n in fact['numbers']}
        supported=lambda selected: quantities_in(' '.join(row['source_text'] for row in selected))
        if needed<=supported(rows):continue
        for row in rows:
            first,last=row['pdf_page_start'],row['pdf_page_end_inclusive']
            old=row['source_text'];quote=old.strip()
            if first!=last or not 1<=first<=len(pages) or not quote or quote[-1] in '.!?;:':continue
            page=pages[first-1];start=page.find(quote)
            if start<0 or page.find(quote,start+1)>=0:continue
            tail=page[start+len(quote):]
            # A new capitalized sentence is not a continuation of the quote.
            if not re.match(r'\s+[a-z]',tail):continue
            ending=re.search(r'[.!?](?=\s|$)',tail[:400])
            if ending is None:continue
            expanded=page[start:start+len(quote)+ending.end()]
            candidate={**row,'source_text':expanded}
            selected=[candidate if item is row else item for item in rows]
            if not needed<=supported(selected):continue
            # Also keep the explicit numeric-token guard used by validate_report.
            if not set(n.replace(',','') for n in fact['numbers'])<=numbers_in(' '.join(item['source_text'] for item in selected)):continue
            row['source_text']=expanded
            changes.append({'fact_id':fact['fact_id'],'evidence_id':row['evidence_id'],'pdf_page':first,
                            'original_quote':old,'completed_quote':expanded,'method':'exact_same_page_sentence_continuation'})
            break
    return result,changes

"""Detachable offline research crew: independent perspectives, one reviewed report.

No live connection to the parent collective is required while the mission runs.
A crew can operate with a local model or an explicitly configured inference
endpoint. Its report does not automatically rewrite the parent's memory.
"""

from concurrent.futures import ThreadPoolExecutor
from .models import infer

ROLES = {
    'explore': 'Develop a complete plan with concrete evidence.',
    'challenge': 'Seek failure modes, counterexamples, and unknowns.',
    'verify': 'Independently check claims and propose tests.',
}


def run_mission(mission, backend='mock', model=None, base_url=None):
    if not isinstance(mission,dict) or not isinstance(mission.get('brief'),str):
        raise ValueError('Invalid detached mission')
    brief=mission['brief']
    if not 1 <= len(brief.strip()) <= 6000:
        raise ValueError('Invalid mission size')

    def contribute(item):
        role,instruction=item
        result=infer('Detached Borg mission. Role: '+role+'. '+instruction+'\nMission: '+brief,
                     backend,model,base_url)
        return role,result

    with ThreadPoolExecutor(max_workers=3) as crew:
        outcomes=dict(crew.map(contribute,ROLES.items()))
    synthesis='Mission: '+brief+'\nIndependent crew work (untrusted suggestions):\n'+\
              '\n'.join(f'{role}: {answer}' for role,answer in outcomes.items())+\
              '\nCombine into one evidence-focused mission report and distinguish uncertainty.'
    final=infer(synthesis,backend,model,base_url)
    return {**mission,'report':final,'crew_results':outcomes,
            'disconnected_research':True,'review_required':True}

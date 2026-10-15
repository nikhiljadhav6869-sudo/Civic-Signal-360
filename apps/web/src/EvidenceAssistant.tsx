import {useState} from 'react';
import {Sparkles} from 'lucide-react';
import {Badge} from './components';
import {evidenceQuestions, explainCase, type EvidenceQuestion} from './caseExplanation';

export function EvidenceAssistant({detail}:{detail:any}) {
  const [question,setQuestion]=useState<EvidenceQuestion>('summary');
  const answer=explainCase(detail,question);

  return <section className="evidence-assistant" aria-labelledby="evidence-assistant-title">
    <div className="assistant-intro">
      <span className="assistant-mark"><Sparkles size={17}/></span>
      <div><h3 id="evidence-assistant-title">Evidence assistant</h3><p>Choose a review question. Answers use only this case’s authorized records.</p></div>
      <Badge type="violet">Deterministic</Badge>
    </div>
    <div className="assistant-questions" role="group" aria-label="Evidence review questions">
      {evidenceQuestions.map(item=><button key={item.id} className={question===item.id?'active':''} aria-pressed={question===item.id} onClick={()=>setQuestion(item.id)}>{item.label}</button>)}
    </div>
    <div className="assistant-answer" aria-live="polite">
      <h4>{answer.title}</h4>
      <ul>{answer.points.map((point,index)=><li key={index}>{point}</li>)}</ul>
      <div className="assistant-sources"><strong>Source IDs</strong>{answer.sources.map(source=><span key={source.id}><code>{source.id}</code> {source.label}</span>)}</div>
      <p className="helper">{answer.caveat}</p>
    </div>
  </section>;
}

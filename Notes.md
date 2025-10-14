Development notes:

Prompt
reduced prompt size to avoid context exhaustion
    do generation per microservice
    removed microservice redeclaration and use only its name to reference it from the list of microservices
    include context prompt before every generation (~2300 tokens)
    change from yaml to json output to avoid indentation problems
    Using manually generated templates on larger (13b) models in json style
    do a second pass afterwards
    use <s>[INST]...[\INST] format for prompts 
    on a second try reduce the context description of microservices and focus on the specific one we are dealing with, this gives the context and the focus possibly reducing context size
LLM configuration
    several models explored codellama 7b, 13b, 34b, meta-llama3-3b,meta-llama3-3b-instruct, meta-llama3-1b
    
Models in general
    Codellama refuses to generate code 
    small models 1.5b,3b, 7b hallucinate 

Minikube must be installed
Kubescape must be installed
Docker must be installed
Anthropic must be installed





DOMANDE

1. Menziona un working manifest. MWC o GT?
2. Distanza contabilizzando le cose che mancano, extra e diverse come nella mia misura ma senza il livello di criticita? 
3. L'idea allora del MWC viene eliminata e solo si evincerà dal lavoro quali sono gli elementi che servono per la generazione? In questo caso non avrò una linea guida per determinare come trovare queste cose.

RICONFERME
1. Non faccio manifesti manuali. OK
2. Si parte da un IR, non provo a fare una generazione disistrutturata e assumo che non funzionerà.
3. L'evaluazione è a n stadi: 
    Pre info aggiunta, post info aggiunta, ..., post n info aggiunta. 
4. contabilizzo la quantità d'interventi necessari per farlo girare.

automatizzata col minimo intervento umano 
con llm o deterministica affidabile non è problema
alcune info sono necessariamente manuali 
altre info relative al environment 

noon kubescape perche è giaabastanza complesso senza la generazione con 

due fattori uno 
valore aggiunto che llm che puo dare: migration towards AI based prompting, 

caratteristiche del manifesto finale
1. manifesto e benformato
2. i servizi non crashano
3. deve funzionare 50 fa quello che voglio analisi esperto e diff con gt
deve avere tutte le caratteristichepresenti nel dockerfile 25%
4. ha tutti gli elementi che kubescape consiglia 25%

il pezzo aggiunto manualmente si poteva aggiungere inspezionando il codice?




https://github.com/docker/getting-started-todo-app
MT2Robs LITE - Farm de Energias + Localizador de Metins/Bosses
================================================================

O QUE E ISTO
  Versao reduzida do bot: SO duas funcoes, ambas 100% client-side
  (o servidor nao ve nada alem do que um jogador normal faria):
    1. ENERGIAS: tu andas, o bot age.
       - Liga "Auto-buy knives" e o Start ESTANDO junto ao vendedor de
         armas: ele compra as facas ate encher o inventario.
       - Depois ANDA TU ate ao alquimista: quando ele esta a vista,
         o bot troca tudo por fragmentos, com ritmo humanizado.
       - Sem auto-buy: troca o que ja tiveres no inventario.
    2. LOCALIZADOR: Metins e Bosses com seta indicadora + lista de alvos
       registados (coordenadas, vivo/morto) e "ir ate" (caminha sozinho).
       Filtro de nivel min/max. Alertas com som (desligavel).

COMO INSTALAR (o teu amigo)
  1. Copia "init.py" e a pasta "MT2Robs" para a RAIZ da pasta do jogo
     (a pasta que tem o metin2client.exe).
  2. Precisas do "eXLib.mix" na raiz do jogo (quem te enviou isto diz-te
     onde arranjar a versao compativel com o teu cliente).
  3. Abre o jogo normalmente.

COMO USAR
  + (ou INSERT, ou "+" no chat) ...... abre/fecha a barra com 2 botoes
  SETA PARA BAIXO .................... esconde TUDO (stealth instantaneo)
  Botao 1 (energia) .................. janela do farm de energias
  Botao 2 (bussola) .................. janela do localizador

  Tudo o que o bot faz esta escrito em "mt2robs.txt" na raiz do jogo
  (erros, trocas, alvos encontrados) -- se algo nao funcionar, esse
  ficheiro diz porquê.

NOTAS
  - Suportado: clientes Gameforge atuais (o mesmo que o autor usa).
  - Mapas com NPCs conhecidos: a1 / b1 / c1 (posições do vendedor e do
    alquimista estao em EnergyBot.py -> NPC_POSITIONS; acrescenta outros
    ai).
  - Usa com cabeca: contas novas, sessoes curtas, nao atrapalhes outros
    jogadores. Risco de ban e sempre teu.

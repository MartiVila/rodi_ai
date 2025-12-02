# Com es codifica

## Pq?

Per reduir la memòria utilitzada per definir un estat i fer més escalable i modular el codi

## Dades que volem saber

### Situació trens i estació
#### Dades de tren

- ID Tren ( n trens? )
- Linia? ( Nhi ha 12 o 13 no? )
- Estació o via (0 o 1)
- Quina estació/Via (Id de la estació o via)
- Estat (Anant, parat, espatllat) (0-2)
- delay (en minuts? 3 xifres?)

>**Considerar**:
>
> Crec que necessitarem alguna mena d'indicar la direcció
>
> Si fem nomes barcelona podem fer bits de validació per trens \
>   Suposem que dins barcelona hi ha un màxim de (exemple) 10 trens, i indiquem quants trens hi ha i que eviti mirar els demes

#### Dades Estació

- Id Estació
- Ocupada

Entre cada un d'ells podriem posar un codi rollo 0000 o algo així per definir un canvi de mini situacio (de tren)


### Dades Globals

- Hora, minut, segon dia (?  afegiria molts estats extres, potser molt semblants, podriem fer que anes de 30 en 30 min)
- num trens operatius (?)



> El de TNUI fa un LRF per reduir numero de paràmetres

Redueixes a què està connectat cada neurona
En el seu cas, una naurona està conectada (exemple)  els primer 25 bits i la segona als mateixos 25 però treien la primera columna i sumantli a darrera



POTSER val la pena fer una dimensió per a cada tren i que es faci encoding de la seva situació personal (origen destí, desti ocupat, etc) NO SE SI QUEDARA MOLT GRAN



Si anessim per linia ja no caldria guardar en quina linea està
entenc k origen i destí no és tant important si simplement posem un bit de direcció
caldira bit de validació davant de cada tren

Posem un bit per dir en quin numero de parada està
Dins dels estats globals (al principi del encoding) posar len de linia en numero d'estacions


num_estacions (2_10) num_trens (2_10) (per tren) bit validació(un), id_tren(4digits? es podria normalitzar?), direcció(1 bit), num node(2 bits), estat_proxima_estació(1bit) 

--> Potser podriem unificar d'alguna manera que el id del tren no influeixi a la decisió de la IA




---> Pensar en codificar el minim possible

--> AL estat s'ha d'intentar generalitzar el màxim possible per tal de trobar més situacions semblants i poder entrenar més eficaçment la IA

Reduir el numero de info que passem , nomes la necessaria
podriem simplement no posar numero de tren

Pq i si nomes fessim IA per a cada punt (estació) i a la hora de fer l'encoding passesim els desviaments ab les distàncis?

Moltes situacions es generalitzarien, però la IA mai tindria un valor exacte de retorn del enviroment pq el fariem passar per diferentes situacions





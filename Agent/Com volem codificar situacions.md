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

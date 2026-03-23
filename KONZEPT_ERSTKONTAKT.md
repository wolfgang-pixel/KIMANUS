# KIMANUS - Erstkontakt & Onboarding Konzept

## Grundprinzip
**Keine Registrierung. Keine E-Mail. Kein Passwort. Nur dein Vorname.**

Das unterscheidet KIMANUS von ALLEN anderen Apps/Diensten:
- Kein Account erstellen
- Keine persoenlichen Daten vorab
- Progressive Freischaltung wie im echten Leben

## Ablauf Erstkontakt

### 1. App oeffnen (erster Besuch)
- User sieht die KIMANUS Oberflaeche
- Tippt auf den roten Chat-Button
- Waehlt: KIM (weiblich) oder KAI (maennlich)

### 2. Begruessung durch KIM/KAI
```
KIM: "Hallo! Ich bin KIM, deine persoenliche Assistentin.
      Wie darf ich dich nennen?"

User: "Monika"

KIM: "Freut mich, Monika! Das ist alles was ich brauche.
      Keine E-Mail, kein Passwort, keine persoenlichen Daten.
      Nur du und ich. Was kann ich fuer dich tun?"
```

### 3. Technisch im Hintergrund
- Geraete-Token wird automatisch generiert (zufaelliger Schluessel)
- Vorname wird im Memory gespeichert
- Token + Vorname = Wiedererkennung beim naechsten Besuch
- KEINE persoenlichen Daten, KEINE Tracking-Daten

### 4. Datenschutz-Hinweis (im Chat, nicht als Popup)
```
KIM: "Uebrigens: Ich speichere keine persoenlichen Daten -
      nur deinen Vornamen und was du mir im Laufe der Zeit erzaehlst.
      Du kannst jederzeit alles einsehen und loeschen. ⚙️"
```

## Progressive Freischaltung (wie im echten Leben)

### Stufe 1: Vorname (sofort)
- KIM/KAI kennt nur den Vornamen
- Chat funktioniert voll
- Memory wird aufgebaut durch Gespraeche

### Stufe 2: E-Mail (nur wenn noetig)
- User will etwas per E-Mail geschickt bekommen
- KIM fragt: "Monika, soll ich dir das per E-Mail schicken? Dann braeuchte ich deine Adresse."
- User gibt E-Mail -> KIM fragt: "Darf ich das speichern?"
- Wird im Memory gespeichert, jederzeit loeschbar

### Stufe 3: Telefon (nur wenn noetig)
- User will angerufen werden oder KIM soll anrufen
- KIM fragt: "Monika, wie ist deine Nummer?"
- Gleiche Logik: Nur auf Nachfrage, nur mit Erlaubnis

### Stufe 4: Weitere Infos (organisch)
- Adresse (wenn Lieferung/Navigation noetig)
- Geburtstag (wenn User es erwaehnt)
- Interessen (lernt KIM automatisch aus Gespraechen)
- ALLES einsehbar und loeschbar im Memory ⚙️

## Wiedererkennung

### Gleiches Geraet, naechster Besuch
- Geraete-Token im Browser gespeichert
- KIM/KAI erkennt: "Das ist Monika"
- Begruessung: "Hallo Monika, schoen dass du wieder da bist!"

### Neues Geraet
- Kein Token vorhanden
- KIM/KAI fragt nochmal nach dem Vornamen
- Optional: QR-Code scannen um Profil zu uebertragen

### WhatsApp / Telefon / E-Mail
- Gleicher KIM/KAI Agent im Hintergrund (n8n)
- Erkennung ueber Telefonnummer/E-Mail (wenn bekannt)
- Gleiches Memory, gleiche Persoenlichkeit

## Was wir speichern

| Was | Wo | Pflicht |
|-----|-----|---------|
| Geraete-Token | Browser + Server | Automatisch |
| Vorname | Server (Memory) | Erstkontakt |
| E-Mail | Server (Memory) | Nur auf Nachfrage |
| Telefon | Server (Memory) | Nur auf Nachfrage |
| Chat-Verlauf | Server | Automatisch |
| Memory-Eintraege | Server | Durch Gespraeche |

## Was wir NICHT speichern
- Keine IP-Adressen
- Kein Browser-Fingerprinting
- Keine Tracking-Cookies
- Keine Standortdaten (ausser User erlaubt es)
- Keine Daten an Dritte

## Der Schluessel
> "Nicht wie ueberall muss ich erst mal alle Daten auf den Tisch blaettern,
> bevor ich irgendwas machen kann." - Wolfgang

KIMANUS dreht die Logik um:
1. Erst Vertrauen aufbauen
2. Dann - nur wenn noetig - mehr erfahren
3. Immer transparent, immer loeschbar
4. Wie ein echter Mensch, nicht wie eine App

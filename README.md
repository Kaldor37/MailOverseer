Mail Overseer
=====================

Mail overseer est un petit gestionnaire de mails sous forme de daemon.
Il se connecte à un serveur IMAP et réalise diverses opérations sur vos mails.

- Version 0.1 : calcule le nombre total de mails non lus sur un serveur IMAP et appelle une commande système à chaque changement.

## Configuration

 Structure du fichier de configuration **$HOME/.config/mail-overseer.conf** :

    ; Configuration pour la connexion au serveur imap
    [imap]
    server = server.imap.com
    login = user@imap.com
    password = [password]

    ; Configuration du gestionnaire
    [overseer]
    ; Niveau de logs minimum
    log_level = INFO
    ; Commande appelée au changement de nombre de mails non lus (facultatif)
    unseen_command = /home/dgabard/bin/mailnotify
    ; Liste des boites mails dont on ne doit pas tenir compte pour le calcul du nombre de mails non lus (facultatif)
    mailbox_blacklist = &AMk-l&AOk-ments envoy&AOk-s;&AMk-l&AOk-ments supprim&AOk-s;Journal

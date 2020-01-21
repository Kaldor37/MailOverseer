Mail Overseer
=====================

Mail overseer est un petit gestionnaire de mails.
Il se connecte à un serveur IMAP et réalise diverses opérations sur vos mails.

* Version 0.1 :
    * Calcule le nombre total de mails non lus sur un serveur IMAP
    * Possibilité d'appeler une commande système à chaque changement
* Version 0.2 : icône dans la barre des tâches
    * L'icône change fonction de la lecture de la boite mail
    * Possibilité de rafraichir dans le menu du clic droit
    * Possibilité d'appeler une commande système au clic sur l'icône (pour focus votre programme de messagerie par exemple)
* Version 0.3 : affichage du nombre de mails non lus dans l'icône

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

    ; Configuration de l'icône de la barre des tâches
    [tray]
    ; Commande à appeler au moment du click sur l'icône
    on_click_command = thunderbird

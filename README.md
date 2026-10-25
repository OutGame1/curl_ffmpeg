# curl_ffmpeg

Application Windows permettant de télécharger des vidéos à partir de commandes cURL récupérées dans un navigateur, en utilisant FFmpeg.

L'application dispose d'une interface graphique, d'une file d'attente de téléchargements et d'un système de sauvegarde de cette file.

## Fonctionnalités

- **Import de commandes cURL** : récupération des informations nécessaires à l'accès aux flux vidéo.
- **Téléchargement HLS** : utilisation de FFmpeg pour récupérer et assembler les segments vidéo.
- **File d'attente** : gestion de plusieurs téléchargements successifs.
- **Sauvegarde de la file** : conservation des téléchargements en attente dans `file_attente.json`.
- **Métadonnées** : organisation des vidéos avec leur titre, leur saison et leur épisode.
- **Formats de sortie** : choix entre MKV et MP4.
- **Copie des flux** : utilisation de `-c copy` pour éviter un réencodage lorsque les flux et le conteneur le permettent.
- **Démarrage sans terminal** : lancement de l'interface graphique grâce au raccourci `start.lnk`.

## Prérequis

- Windows
- Python 3
- FFmpeg accessible depuis le `PATH`
- PowerShell pour exécuter le script d'installation

## Installation

1. Télécharger ou décompresser le projet dans un dossier.
2. Ouvrir PowerShell dans le dossier `curl_ffmpeg`.
3. Exécuter le script d'installation :

   ```powershell
   .\install.ps1
   ```

Le script d'installation est prévu pour préparer l'environnement nécessaire et créer le raccourci `start.lnk` à la racine du projet.

Si Windows bloque l'exécution du script, vérifie la politique d'exécution PowerShell appliquée à ton système avant de modifier ses paramètres.

## Démarrage

Après l'installation, double-cliquer sur :

```text
start.lnk
```

L'application est lancée avec `pythonw.exe`, ce qui évite l'ouverture d'une fenêtre de terminal.

## Utilisation

### 1. Récupérer une commande cURL

1. Ouvrir la page contenant le lecteur vidéo dans ton navigateur.
2. Ouvrir les outils de développement du navigateur, puis l'onglet **Réseau** (*Network*).
3. Lancer la lecture de la vidéo.
4. Identifier la requête correspondant au manifeste ou au flux HLS.
5. Utiliser l'option **Copier en tant que cURL** (*Copy as cURL*).

### 2. Ajouter un téléchargement

1. Coller la commande cURL dans l'application.
2. Renseigner les métadonnées souhaitées : titre, saison et épisode.
3. Sélectionner le format de sortie.
4. Ajouter le téléchargement à la file d'attente.

### 3. Lancer les téléchargements

Les téléchargements sont traités par la file d'attente selon le fonctionnement de l'application. FFmpeg récupère les flux et assemble la vidéo dans le conteneur sélectionné, sans réencodage lorsque c'est possible.

### 4. Reprendre son travail

La file d'attente est sauvegardée dans `file_attente.json`. Ce fichier permet de conserver les informations des téléchargements en attente entre les sessions, selon l'état enregistré par l'application.

## Structure du projet

```text
curl_ffmpeg/
├── install.ps1
├── uninstall.ps1
├── start.lnk
├── README.md
├── .gitignore
└── src/
    ├── __init__.py
    ├── app.py
    ├── config.py
    ├── curl_parser.py
    ├── hls.py
    ├── queue_worker.py
    ├── queue_persistence.py
    └── queue_editor.py
```

Le fichier `start.lnk` est généré par le script d'installation ; il n'est donc pas nécessaire de le distribuer dans les sources.

## Dépendances

### Python

Le code de l'application se trouve dans le dossier `src`.

Le module principal est `src.app`. Le point d'entrée de `src/app.py` doit initialiser l'application graphique et lancer sa boucle principale.

### FFmpeg

FFmpeg est utilisé pour télécharger et assembler les flux vidéo.

L'option de copie des flux (`-c copy`) évite le réencodage, mais elle ne garantit pas que tous les flux soient compatibles avec tous les conteneurs de sortie.

## Dépannage

### Le téléchargement échoue

- Vérifie que la commande cURL est complète.
- Vérifie que les cookies, jetons et en-têtes requis sont encore valides.
- Vérifie que le flux est accessible et que FFmpeg prend en charge le protocole utilisé.
- Consulte les erreurs affichées par FFmpeg.

### Le MP4 ne peut pas être généré

Certains codecs ou flux ne sont pas compatibles avec le conteneur MP4. Essayer le format MKV ou vérifier la compatibilité des flux avant de modifier les paramètres de téléchargement.

## Désinstallation

Exécuter le script fourni :

```powershell
.\uninstall.ps1
```

document.addEventListener('DOMContentLoaded', () => {
    let currentUser = null;
    let projectFiles = [];

    const googleLoginBtn = document.getElementById('google-login-btn');
    const userProfile = document.getElementById('user-profile');
    const userName = document.getElementById('user-name');
    const userAvatar = document.getElementById('user-avatar');
    
    const chatInput = document.getElementById('chat-input');
    const chatSubmit = document.getElementById('chat-submit');
    const chatMessages = document.getElementById('chat-messages');
    const chatForm = document.getElementById('chat-form');
    
    const tabChat = document.getElementById('tab-chat');
    const tabFiles = document.getElementById('tab-files');
    const viewChat = document.getElementById('view-chat');
    const viewFiles = document.getElementById('view-files');
    const fileList = document.getElementById('file-list');
    
    const codeContainer = document.getElementById('code-container');
    const previewContainer = document.getElementById('preview-container');
    const codeViewer = document.getElementById('code-viewer');
    const webPreview = document.getElementById('web-preview');
    const btnViewCode = document.getElementById('btn-view-code');
    const btnViewPreview = document.getElementById('btn-view-preview');
    
    const currentFilename = document.getElementById('current-filename');
    const btnDownload = document.getElementById('btn-download');
    const loadingOverlay = document.getElementById('loading-overlay');

    const btnNewChat = document.getElementById('btn-new-chat');
    const btnEditCode = document.getElementById('btn-edit-code');
    const btnSaveCode = document.getElementById('btn-save-code');
    const codeEditor = document.getElementById('code-editor');
    const preViewer = document.getElementById('pre-viewer');

    const clientIdMeta = document.querySelector('meta[name="google-client-id"]').content;
    
    if (clientIdMeta && clientIdMeta !== "None" && clientIdMeta !== "") {
        google.accounts.id.initialize({
            client_id: clientIdMeta,
            callback: handleCredentialResponse
        });
        google.accounts.id.renderButton(googleLoginBtn, { theme: "filled_black", size: "medium", shape: "pill" });
    }

    async function handleCredentialResponse(response) {
        try {
            const res = await fetch('/api/auth/google', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: response.credential })
            });
            const data = await res.json();
            
            if (data.success) {
                currentUser = data.user;
                googleLoginBtn.classList.add('hidden');
                userProfile.classList.remove('hidden');
                userName.textContent = currentUser.nombre_completo;
                userAvatar.src = currentUser.foto_perfil;
                
                chatInput.disabled = false;
                chatSubmit.disabled = false;
                btnDownload.classList.remove('hidden');
                btnNewChat.classList.remove('hidden');
                
                loadChatHistory();
            }
        } catch (error) {
            console.error("Error en autenticación:", error);
        }
    }

    async function loadChatHistory() {
        chatMessages.innerHTML = '<div class="text-center text-gray-500 text-sm mt-4">Cargando historial...</div>';
        try {
            const res = await fetch(`/api/chat/history?usuario_id=${currentUser.id}`);
            const data = await res.json();
            
            chatMessages.innerHTML = '';
            if (data.historial && data.historial.length > 0) {
                data.historial.forEach(msg => appendMessage(msg.role, msg.text));
            } else {
                chatMessages.innerHTML = '<div class="text-center text-gray-500 text-sm mt-4">Comienza describiendo tu proyecto.</div>';
            }
            
            if (data.archivos && data.archivos.length > 0) {
                projectFiles = data.archivos;
                renderFileList();
                displayCode(projectFiles[0]);
            }
        } catch (error) {
            chatMessages.innerHTML = '<div class="text-center text-red-500 text-sm mt-4">Error al cargar historial.</div>';
        }
    }

    tabChat.addEventListener('click', () => {
        viewChat.classList.remove('hidden');
        viewFiles.classList.add('hidden');
        tabChat.classList.replace('text-gray-400', 'text-blue-400');
        tabChat.classList.replace('hover:text-gray-200', 'border-blue-400');
        tabChat.classList.add('border-b-2', 'bg-gray-700');
        tabFiles.classList.remove('border-b-2', 'bg-gray-700', 'text-blue-400', 'border-blue-400');
        tabFiles.classList.add('text-gray-400', 'hover:text-gray-200');
    });

    tabFiles.addEventListener('click', () => {
        viewFiles.classList.remove('hidden');
        viewChat.classList.add('hidden');
        tabFiles.classList.replace('text-gray-400', 'text-blue-400');
        tabFiles.classList.replace('hover:text-gray-200', 'border-blue-400');
        tabFiles.classList.add('border-b-2', 'bg-gray-700');
        tabChat.classList.remove('border-b-2', 'bg-gray-700', 'text-blue-400', 'border-blue-400');
        tabChat.classList.add('text-gray-400', 'hover:text-gray-200');
    });

    btnViewCode.addEventListener('click', () => {
        codeContainer.classList.remove('hidden');
        previewContainer.classList.add('hidden');
    });

    btnViewPreview.addEventListener('click', () => {
        codeContainer.classList.add('hidden');
        previewContainer.classList.remove('hidden');
        renderWebPreview();
    });

    function renderWebPreview() {
        let htmlFile = projectFiles.find(f => f.ruta.endsWith('.html'));
        if (!htmlFile) {
            webPreview.srcdoc = '<div style="font-family:sans-serif;padding:20px;">No se encontró ningún archivo HTML para previsualizar. Pídele a la IA que genere uno.</div>';
            return;
        }

        let previewContent = htmlFile.contenido;
        
        projectFiles.forEach(f => {
            if (f.ruta.endsWith('.css')) {
                const cssTag = `<style>${f.contenido}</style>`;
                const regexCss = new RegExp(`<link[^>]*href=["'].*?${f.ruta.split('/').pop()}["'][^>]*>`, 'g');
                if (regexCss.test(previewContent)) {
                    previewContent = previewContent.replace(regexCss, cssTag);
                } else {
                    previewContent = previewContent.replace('</head>', `${cssTag}</head>`);
                }
            }
            if (f.ruta.endsWith('.js')) {
                const jsTag = `<script>${f.contenido}</script>`;
                const regexJs = new RegExp(`<script[^>]*src=["'].*?${f.ruta.split('/').pop()}["'][^>]*><\\/script>`, 'g');
                if (regexJs.test(previewContent)) {
                    previewContent = previewContent.replace(regexJs, jsTag);
                } else {
                    previewContent = previewContent.replace('</body>', `${jsTag}</body>`);
                }
            }
        });

        webPreview.srcdoc = previewContent;
    }

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const prompt = chatInput.value.trim();
        if (!prompt || !currentUser) return;

        appendMessage('user', prompt);
        chatInput.value = '';
        loadingOverlay.classList.remove('hidden');

        try {
            const res = await fetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: prompt, usuario_id: currentUser.id })
            });
            const data = await res.json();
            
            loadingOverlay.classList.add('hidden');
            
            if (data.success) {
                appendMessage('agent', data.resultado_orquestador);
                
                if (data.archivos_actualizados && data.archivos_actualizados.length > 0) {
                    updateFileExplorer(data.archivos_actualizados);
                }
            } else {
                appendMessage('agent', `Error: ${data.error}`);
            }
        } catch (error) {
            loadingOverlay.classList.add('hidden');
            appendMessage('agent', 'Ocurrió un error de conexión con el servidor.');
        }
    });

    function appendMessage(role, text) {
        const div = document.createElement('div');
        div.className = `p-3 rounded-lg text-sm whitespace-pre-wrap ${role === 'user' ? 'bg-blue-900/30 ml-4 border border-blue-800' : 'bg-gray-700 mr-4 border border-gray-600'}`;
        
        let displayText = text;
        if (role === 'agent') {
             displayText = text.replace(/```[\s\S]*?```/g, '[Código procesado y actualizado en el Explorador]');
        }

        div.textContent = displayText;
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function updateFileExplorer(archivos) {
        archivos.forEach(nuevoArchivo => {
            const existe = projectFiles.findIndex(f => f.ruta === nuevoArchivo.ruta);
            if (existe !== -1) {
                projectFiles[existe] = nuevoArchivo;
            } else {
                projectFiles.push(nuevoArchivo);
            }
        });

        renderFileList();
        
        if (archivos.length > 0) {
            displayCode(archivos[0]);
        }
        
        tabFiles.click();
    }

    function renderFileList() {
        fileList.innerHTML = '';
        if (projectFiles.length === 0) {
            fileList.innerHTML = '<li class="px-4 py-2 text-gray-500">No hay archivos aún.</li>';
            return;
        }

        projectFiles.forEach(archivo => {
            const li = document.createElement('li');
            li.className = 'px-4 py-2 hover:bg-gray-600 cursor-pointer flex items-center gap-2 truncate transition-colors';
            
            let icon = '📄';
            if (archivo.ruta.endsWith('.py')) icon = '🐍';
            else if (archivo.ruta.endsWith('.html')) icon = '🌐';
            else if (archivo.ruta.endsWith('.js')) icon = '💛';
            else if (archivo.ruta.endsWith('.css')) icon = '🎨';

            li.innerHTML = `<span>${icon}</span> <span class="truncate">${archivo.ruta}</span>`;
            
            li.addEventListener('click', () => displayCode(archivo));
            fileList.appendChild(li);
        });
    }

    function displayCode(archivo) {
        currentFilename.textContent = archivo.ruta;
        
        let lang = 'plaintext';
        if (archivo.ruta.endsWith('.py')) lang = 'python';
        else if (archivo.ruta.endsWith('.html')) lang = 'html';
        else if (archivo.ruta.endsWith('.js')) lang = 'javascript';
        else if (archivo.ruta.endsWith('.css')) lang = 'css';

        codeViewer.className = `language-${lang} h-full p-4 text-sm font-mono bg-transparent`;
        codeViewer.textContent = archivo.contenido;
        codeEditor.value = archivo.contenido; // Sincronizamos el editor manual
        
        hljs.highlightElement(codeViewer);

        // Mostramos botón de editar, ocultamos el de guardar
        btnEditCode.classList.remove('hidden');
        btnSaveCode.classList.add('hidden');
        codeEditor.classList.add('hidden');
        preViewer.classList.remove('hidden');
    }
    // 4. Lógica para EDITAR a mano:
    btnEditCode.addEventListener('click', () => {
        preViewer.classList.add('hidden');
        codeEditor.classList.remove('hidden');
        btnEditCode.classList.add('hidden');
        btnSaveCode.classList.remove('hidden');
    });

    // 5. Lógica para GUARDAR los cambios manuales:
    btnSaveCode.addEventListener('click', async () => {
        if (!currentUser) return;
        const rutaActual = currentFilename.textContent;
        const nuevoContenido = codeEditor.value;

        try {
            const res = await fetch('/api/file/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ usuario_id: currentUser.id, ruta: rutaActual, contenido: nuevoContenido })
            });
            
            if(res.ok) {
                // Actualizamos la memoria del frontend
                const archivoIndex = projectFiles.findIndex(f => f.ruta === rutaActual);
                if (archivoIndex !== -1) projectFiles[archivoIndex].contenido = nuevoContenido;
                
                // Volvemos al modo vista
                displayCode({ruta: rutaActual, contenido: nuevoContenido});
                alert("Cambios guardados correctamente.");
            }
        } catch (error) {
            alert("Error al guardar el archivo.");
        }
    });

    // 6. Lógica de NUEVO PROYECTO:
    btnNewChat.addEventListener('click', async () => {
        if (!currentUser) return;
        const confirmar = confirm("¿Estás segura? Esto borrará el chat actual y los archivos generados para iniciar un proyecto en blanco y ahorrar memoria.");
        
        if (confirmar) {
            await fetch('/api/chat/new', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ usuario_id: currentUser.id })
            });
            
            // Limpiamos la interfaz
            chatMessages.innerHTML = '<div class="text-center text-gray-500 text-sm mt-4">Nuevo proyecto iniciado. Comienza a describir lo que necesitas.</div>';
            projectFiles = [];
            renderFileList();
            codeViewer.textContent = '# El código generado aparecerá aquí';
            currentFilename.textContent = 'selecciona_un_archivo.py';
            btnEditCode.classList.add('hidden');
        }
    });

    btnDownload.addEventListener('click', () => {
        if (!currentUser) return;
        if (projectFiles.length === 0) {
            alert("No hay archivos para descargar aún.");
            return;
        }
        
        // Aquí le preguntamos el nombre al usuario:
        const nombreElegido = prompt("¿Qué nombre le quieres poner a tu proyecto?", "Proyecto_Cosméticos");
        
        if (nombreElegido !== null) { // Si no le dio a cancelar
            window.location.href = `/api/download/${currentUser.id}?nombre=${encodeURIComponent(nombreElegido)}`;
        }
    });
});
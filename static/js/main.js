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
    const btnCancelEdit = document.getElementById('btn-cancel-edit');
    const preViewer = document.getElementById('pre-viewer');

    const btnToggleSidebar = document.getElementById('btn-toggle-sidebar');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebar-overlay');

    const clientIdMeta = document.querySelector('meta[name="google-client-id"]').content;
   
    function showModal(title, message, type = 'alert', defaultValue = '') {
        return new Promise((resolve) => {
            const modal = document.getElementById('custom-modal');
            const modalContent = document.getElementById('modal-content');
            const inputEl = document.getElementById('modal-input');
            const btnCancel = document.getElementById('modal-btn-cancel');
            const btnConfirm = document.getElementById('modal-btn-confirm');

            document.getElementById('modal-title').textContent = title;
            document.getElementById('modal-message').textContent = message;
            
            inputEl.value = defaultValue;
            inputEl.classList.add('hidden');
            btnCancel.classList.add('hidden');

            if (type === 'prompt') {
                inputEl.classList.remove('hidden');
                btnCancel.classList.remove('hidden');
            } else if (type === 'confirm') {
                btnCancel.classList.remove('hidden');
            }

            modal.classList.remove('hidden');
            setTimeout(() => {
                modal.classList.remove('opacity-0');
                modalContent.classList.remove('scale-95');
                if (type === 'prompt') inputEl.focus();
            }, 10);

            const closeModal = () => {
                modal.classList.add('opacity-0');
                modalContent.classList.add('scale-95');
                setTimeout(() => modal.classList.add('hidden'), 200);
                btnConfirm.onclick = null;
                btnCancel.onclick = null;
            };

            btnConfirm.onclick = () => {
                closeModal();
                resolve(type === 'prompt' ? inputEl.value : true);
            };

            btnCancel.onclick = () => {
                closeModal();
                resolve(type === 'prompt' ? null : false);
            };
        });
    }

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
        
        if (role === 'user') {
            div.className = 'p-3 rounded-lg text-sm bg-[#1f2937] border border-gray-700 ml-8 text-gray-200 whitespace-pre-wrap';
            div.textContent = text;
        } else {
            div.className = 'p-0 text-sm mr-8 text-gray-300 chat-markdown';
            // Sustituimos los bloques de código crudos por una cita limpia
            let cleanText = text.replace(/```[\s\S]*?```/g, '\n> ✦ **Código procesado** y sincronizado en el explorador de archivos.\n');
            // Usamos la librería marked para formatear el texto a HTML limpio
            div.innerHTML = marked.parse(cleanText);
        }

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
        btnCancelEdit.classList.add('hidden');
        codeEditor.classList.add('hidden');
        preViewer.classList.remove('hidden');
    }
    // 4. Lógica para EDITAR a mano:
    btnEditCode.addEventListener('click', () => {
        preViewer.classList.add('hidden');
        codeEditor.classList.remove('hidden');
        btnCancelEdit.classList.remove('hidden');
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
                const archivoIndex = projectFiles.findIndex(f => f.ruta === rutaActual);
                if (archivoIndex !== -1) projectFiles[archivoIndex].contenido = nuevoContenido;
                displayCode({ruta: rutaActual, contenido: nuevoContenido});
                
                // Reemplazo del alert
                await showModal("Archivo Guardado", "Los cambios manuales se han aplicado correctamente.", "alert");
            }
            btnCancelEdit.classList.add('hidden');
        } catch (error) {
            await showModal("Error", "Ocurrió un problema al guardar el archivo.", "alert");
        }
    });

    btnCancelEdit.addEventListener('click', () => {
        // Restauramos el contenido original del archivo
        const rutaActual = currentFilename.textContent;
        const archivo = projectFiles.find(f => f.ruta === rutaActual);
        if (archivo) codeEditor.value = archivo.contenido;

        // Regresamos a la vista de lectura
        codeEditor.classList.add('hidden');
        preViewer.classList.remove('hidden');
        
        // Ocultamos los botones de edición y mostramos el original
        btnCancelEdit.classList.add('hidden');
        btnSaveCode.classList.add('hidden');
        btnEditCode.classList.remove('hidden');
    });

    btnNewChat.addEventListener('click', async () => {
        if (!currentUser) return;
        
        // Reemplazo del confirm feo
        const confirmar = await showModal(
            "¿Iniciar nuevo proyecto?", 
            "Esto borrará el chat y los archivos actuales de la vista para iniciar un lienzo en blanco. ¿Deseas continuar?", 
            "confirm"
        );
        
        if (confirmar) {
            await fetch('/api/chat/new', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ usuario_id: currentUser.id })
            });
            
            chatMessages.innerHTML = '';
            appendMessage('agent', 'Lienzo limpio. Describe el nuevo proyecto o la base de datos que deseas crear.');
            projectFiles = [];
            renderFileList();
            codeViewer.textContent = '# El código generado aparecerá aquí';
            currentFilename.textContent = '...';
            btnEditCode.classList.add('hidden');
        }
    });

    btnDownload.addEventListener('click', async () => {
        if (!currentUser) return;
        if (projectFiles.length === 0) {
            await showModal("Proyecto Vacío", "No hay archivos generados para descargar aún.", "alert");
            return;
        }
        
        // Reemplazo del prompt feo por el input personalizado
        const nombreElegido = await showModal(
            "Exportar Proyecto", 
            "Asigna un nombre sin espacios para tu archivo .zip:", 
            "prompt", 
            "Mi_Proyecto"
        );
        
        if (nombreElegido !== null && nombreElegido.trim() !== "") {
            window.location.href = `/api/download/${currentUser.id}?nombre=${encodeURIComponent(nombreElegido)}`;
        }
    });
    // Modificamos un poco el cambio de pestañas del código para cambiar estilos del botón activo
    btnViewCode.addEventListener('click', () => {
        codeContainer.classList.remove('hidden');
        previewContainer.classList.add('hidden');
        btnViewCode.classList.replace('text-gray-400', 'text-blue-400');
        btnViewCode.classList.replace('border-gray-600', 'border-blue-500');
        btnViewCode.classList.add('bg-gray-800');
        
        btnViewPreview.classList.replace('text-blue-400', 'text-gray-400');
        btnViewPreview.classList.replace('border-blue-500', 'border-gray-600');
        btnViewPreview.classList.remove('bg-gray-800');
    });

    btnViewPreview.addEventListener('click', () => {
        codeContainer.classList.add('hidden');
        previewContainer.classList.remove('hidden');
        renderWebPreview();
        
        btnViewPreview.classList.replace('text-gray-400', 'text-blue-400');
        btnViewPreview.classList.replace('border-gray-600', 'border-blue-500');
        btnViewPreview.classList.add('bg-gray-800');
        
        btnViewCode.classList.replace('text-blue-400', 'text-gray-400');
        btnViewCode.classList.replace('border-blue-500', 'border-gray-600');
        btnViewCode.classList.remove('bg-gray-800');
    });
    // Mostrar u ocultar el panel lateral
    btnToggleSidebar.addEventListener('click', () => {
        // Verificamos si estamos en un tamaño de pantalla móvil (< 768px)
        if (window.innerWidth < 768) {
            sidebar.classList.toggle('-translate-x-full');
            sidebarOverlay.classList.toggle('hidden');
        } else {
            // En computadora, aplicamos un margen negativo para deslizarlo fuera del monitor
            sidebar.classList.toggle('md:-ml-96');
        }
    });

    // Cerrar el panel al hacer clic en el área oscura (solo para móviles)
    sidebarOverlay.addEventListener('click', () => {
        sidebar.classList.add('-translate-x-full');
        sidebarOverlay.classList.add('hidden');
    });
});
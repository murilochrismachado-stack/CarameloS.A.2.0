/* ==========================================================
   1. ESTADO DA APLICAÇÃO
   ========================================================== */
const config = window.ENV || {};
let pets = [];
let usuario = null;
let petAberto = null;
let avisoLogin = "";

const $ = (id) => document.getElementById(id);

/* ==========================================================
   2. NAVEGAÇÃO ENTRE ABAS
   ========================================================== */
const abasValidas = ["sobre", "pets", "entrar"];

function mostrarAba() {
  const nome = location.hash.replace("#", "");
  const ativa = abasValidas.includes(nome) ? nome : "sobre";

  document.querySelectorAll(".pagina").forEach((p) => {
    p.classList.toggle("ativa", p.id === "pagina-" + ativa);
  });

  document.querySelectorAll(".aba").forEach((a) => {
    if (a.getAttribute("href") === "#" + ativa) {
      a.setAttribute("aria-current", "page");
    } else {
      a.removeAttribute("aria-current");
    }
  });

  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", mostrarAba);

/* ==========================================================
   3. LISTA DE PETS (Carregados do MySQL via API)
   ========================================================== */
async function carregarPets() {
  try {
    const resposta = await fetch("/api/pets");
    pets = await resposta.json();
    desenharPets("todos");
  } catch (erro) {
    console.error("Erro ao buscar pets:", erro);
    $("lista-pets").textContent = "Não foi possível carregar os pets no momento.";
  }
}

function criarEtiquetas(listaTextos) {
  const container = document.createElement("div");
  container.className = "etiquetas";

  listaTextos.forEach((texto) => {
    const span = document.createElement("span");
    span.textContent = texto;
    container.appendChild(span);
  });

  return container;
}

function desenharPets(filtro) {
  const lista = $("lista-pets");
  lista.innerHTML = "";

  const filtrados = pets.filter((pet) => filtro === "todos" || pet.grupos.includes(filtro));

  filtrados.forEach((pet) => {
    const card = document.createElement("article");
    card.className = "pet";

    const img = document.createElement("img");
    img.src = pet.foto;
    img.alt = pet.fotoAlt;
    img.loading = "lazy";

    const corpo = document.createElement("div");
    corpo.className = "pet-corpo";

    const titulo = document.createElement("h3");
    titulo.textContent = pet.nome;

    const etiquetas = criarEtiquetas(pet.etiquetas);

    const resumo = document.createElement("p");
    resumo.textContent = pet.resumo;

    const botao = document.createElement("button");
    botao.className = "botao";
    botao.type = "button";
    botao.textContent = "Ver detalhes";
    botao.addEventListener("click", () => abrirDetalhes(pet));

    corpo.append(titulo, etiquetas, resumo, botao);
    card.append(img, corpo);
    lista.appendChild(card);
  });
}

document.querySelectorAll(".filtro").forEach((botao) => {
  botao.addEventListener("click", () => {
    document.querySelectorAll(".filtro").forEach((b) => b.setAttribute("aria-pressed", String(b === botao)));
    desenharPets(botao.dataset.filtro);
  });
});

/* ==========================================================
   4. JANELA DE DETALHES E REGISTRO DE ADOÇÃO NO MYSQL
   ========================================================== */
function abrirDetalhes(pet) {
  petAberto = pet;
  $("detalhe-foto").src = pet.foto;
  $("detalhe-foto").alt = pet.fotoAlt;
  $("detalhe-nome").textContent = pet.nome;
  $("detalhe-descricao").textContent = pet.descricao;

  const containerEtiquetas = $("detalhe-etiquetas");
  containerEtiquetas.innerHTML = "";
  pet.etiquetas.forEach((texto) => {
    const span = document.createElement("span");
    span.textContent = texto;
    containerEtiquetas.appendChild(span);
  });

  $("detalhe-aviso").textContent = "";
  $("detalhe").showModal();
}

$("detalhe-fechar").addEventListener("click", () => $("detalhe").close());

$("detalhe").addEventListener("click", (evento) => {
  if (evento.target === $("detalhe")) {
    $("detalhe").close();
  }
});

$("detalhe-adotar").addEventListener("click", async () => {
  if (!usuario) {
    avisoLogin = `Faça login para registrar interesse em adotar ${petAberto.nome}.`;
    $("detalhe").close();
    location.hash = "#entrar";
    atualizarInterfaceLogin();
    return;
  }

  try {
    const resposta = await fetch("/api/adotar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pet_id: petAberto.id })
    });

    const dados = await resposta.json();

    if (resposta.ok && dados.sucesso) {
      $("detalhe-aviso").textContent = `Interesse em ${petAberto.nome} salvo com sucesso! Entraremos em contato.`;

      if (config.ABRIR_WHATSAPP_AO_ADOTAR && config.WHATSAPP_NUMBER) {
        const msg = encodeURIComponent(`Olá! Sou ${usuario} e registrei interesse em adotar o(a) ${petAberto.nome}.`);
        window.open(`https://wa.me/${config.WHATSAPP_NUMBER}?text=${msg}`, "_blank", "noopener,noreferrer");
      }
    } else {
      $("detalhe-aviso").textContent = dados.erro || "Erro ao registrar interesse.";
    }
  } catch (erro) {
    $("detalhe-aviso").textContent = "Falha de conexão com o servidor.";
  }
});

/* ==========================================================
   5. AUTENTICAÇÃO INTEGRADA AO BACK-END
   ========================================================== */
function atualizarInterfaceLogin() {
  const logado = usuario !== null;
  $("form-login").hidden = logado;
  $("area-logado").hidden = !logado;
  $("login-titulo").textContent = logado ? "Olá!" : "Entrar";
  $("login-texto").textContent = logado
    ? `Você entrou como ${usuario}.`
    : avisoLogin || "Acesse sua conta ou cadastre-se automaticamente para adotar.";
  $("aba-entrar").textContent = logado ? "Minha conta" : "Entrar";
}

async function verificarSessaoAtual() {
  try {
    const resposta = await fetch("/api/sessao");
    const dados = await resposta.json();
    usuario = dados.logado ? dados.email : null;
    atualizarInterfaceLogin();
  } catch (erro) {
    console.error("Erro ao verificar sessão:", erro);
  }
}

$("form-login").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const email = $("email").value.trim();
  const senha = $("senha").value;

  try {
    const resposta = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, senha })
    });

    const dados = await resposta.json();

    if (!resposta.ok) {
      $("erro").textContent = dados.erro || "Erro ao entrar.";
      return;
    }

    $("erro").textContent = "";
    avisoLogin = "";
    usuario = dados.email;
    $("form-login").reset();
    atualizarInterfaceLogin();
  } catch (erro) {
    $("erro").textContent = "Erro de conexão com o servidor.";
  }
});

$("sair").addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  usuario = null;
  atualizarInterfaceLogin();
});

/* ==========================================================
   6. INICIALIZAÇÃO
   ========================================================== */
carregarPets();
verificarSessaoAtual();
mostrarAba();
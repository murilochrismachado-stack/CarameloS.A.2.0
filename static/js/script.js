/* ==========================================================
   1. ESTADO DA APLICAÇÃO
   ========================================================== */
let pets = [];
let produtos = [];
let carrinho = [];
let usuario = null;       // { email, tipo }
let petAberto = null;     // pet aberto no modal
let petParaAdotar = null; // pet selecionado para o formulário de adoção
let avisoLogin = "";

const $ = (id) => document.getElementById(id);
const formatarMoeda = (valor) => valor.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

/* ==========================================================
   2. NAVEGAÇÃO ENTRE ABAS
   ========================================================== */
const abasValidas = ["sobre", "pets", "adotar", "loja", "entrar"];

function mostrarAba() {
  const nome = location.hash.replace("#", "");
  const ativa = abasValidas.includes(nome) ? nome : "sobre";

  // Protege a aba de adoção caso nenhum pet esteja selecionado
  if (ativa === "adotar" && (!petParaAdotar || !usuario)) {
    location.hash = "#pets";
    return;
  }

  document.querySelectorAll(".pagina").forEach((p) => {
    p.classList.toggle("ativa", p.id === "pagina-" + ativa);
  });

  document.querySelectorAll(".aba").forEach((a) => {
    const href = a.getAttribute("href");
    const destaque = href === "#" + ativa || (ativa === "adotar" && href === "#pets");
    if (destaque) {
      a.setAttribute("aria-current", "page");
    } else {
      a.removeAttribute("aria-current");
    }
  });

  if (ativa === "entrar" && usuario) {
    carregarDadosPainel();
  }

  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", mostrarAba);

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

/* ==========================================================
   3. LISTA DE PETS E FLUXO DE ADOÇÃO
   ========================================================== */
async function carregarPets() {
  try {
    const resposta = await fetch("/api/pets");
    pets = await resposta.json();
    desenharPets("todos");
  } catch (erro) {
    console.error("Erro ao buscar pets:", erro);
  }
}

function desenharPets(filtro) {
  const lista = $("lista-pets");
  lista.innerHTML = "";

  const filtrados = pets.filter((pet) => filtro === "todos" || pet.grupos.includes(filtro));

  if (filtrados.length === 0) {
    lista.innerHTML = "<p class='subtitulo'>Nenhum pet encontrado nesta categoria no momento.</p>";
    return;
  }

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

document.querySelectorAll("#pagina-pets .filtro").forEach((botao) => {
  botao.addEventListener("click", () => {
    document.querySelectorAll("#pagina-pets .filtro").forEach((b) => b.setAttribute("aria-pressed", String(b === botao)));
    desenharPets(botao.dataset.filtro);
  });
});

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
$("detalhe").addEventListener("click", (e) => {
  if (e.target === $("detalhe")) $("detalhe").close();
});

// Clique em "Quero adotar" -> Vai para login ou para a aba de endereço e vacinas
$("detalhe-adotar").addEventListener("click", () => {
  if (!usuario) {
    avisoLogin = `Faça login para preencher o formulário de adoção de ${petAberto.nome}.`;
    $("detalhe").close();
    location.hash = "#entrar";
    atualizarInterfaceLogin();
    return;
  }

  petParaAdotar = petAberto;
  $("detalhe").close();
  $("adotar-titulo").textContent = `Adotar ${petParaAdotar.nome}`;
  $("adotar-subtitulo").textContent = `Informe o endereço do novo lar de ${petParaAdotar.nome} e o plano de vacinas.`;
  $("adotar-erro").textContent = "";
  location.hash = "#adotar";
});

// Envio do Formulário de Adoção
$("form-adotar").addEventListener("submit", async (e) => {
  e.preventDefault();
  const endereco = $("adotar-endereco").value.trim();
  const vacinas = $("adotar-vacinas").value.trim();

  if (!endereco || !vacinas) {
    $("adotar-erro").textContent = "Por favor, preencha o endereço e as informações de vacinação.";
    return;
  }

  try {
    const resposta = await fetch("/api/adotar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pet_id: petParaAdotar.id,
        endereco,
        vacinas
      })
    });
    const dados = await resposta.json();

    if (!resposta.ok) {
      $("adotar-erro").textContent = dados.erro || "Erro ao registrar adoção.";
      return;
    }

    $("form-adotar").reset();
    petParaAdotar = null;
    await carregarPets();
    location.hash = "#entrar";
  } catch (erro) {
    $("adotar-erro").textContent = "Erro de conexão com o servidor.";
  }
});

/* ==========================================================
   4. LOJA (RAÇÕES E BRINQUEDOS) + CARRINHO
   ========================================================== */
async function carregarProdutos() {
  try {
    const resposta = await fetch("/api/produtos");
    produtos = await resposta.json();
    desenharProdutos("todos");
  } catch (erro) {
    console.error("Erro ao carregar loja:", erro);
  }
}

function desenharProdutos(filtro) {
  const lista = $("lista-produtos");
  lista.innerHTML = "";

  const filtrados = produtos.filter((p) => filtro === "todos" || p.grupos.includes(filtro));

  filtrados.forEach((prod) => {
    const card = document.createElement("article");
    card.className = "pet";

    const img = document.createElement("img");
    img.src = prod.foto;
    img.alt = prod.nome;
    img.loading = "lazy";

    const corpo = document.createElement("div");
    corpo.className = "pet-corpo";

    const titulo = document.createElement("h3");
    titulo.textContent = prod.nome;

    const etiquetas = criarEtiquetas(prod.etiquetas);

    const resumo = document.createElement("p");
    resumo.textContent = prod.resumo;

    const preco = document.createElement("div");
    preco.className = "preco-destaque";
    preco.textContent = formatarMoeda(prod.preco);

    const botao = document.createElement("button");
    botao.className = "botao";
    botao.type = "button";
    botao.textContent = "Adicionar ao carrinho";
    botao.addEventListener("click", () => adicionarAoCarrinho(prod));

    corpo.append(titulo, etiquetas, resumo, preco, botao);
    card.append(img, corpo);
    lista.appendChild(card);
  });
}

document.querySelectorAll(".filtro-loja").forEach((botao) => {
  botao.addEventListener("click", () => {
    document.querySelectorAll(".filtro-loja").forEach((b) => b.setAttribute("aria-pressed", String(b === botao)));
    desenharProdutos(botao.dataset.filtro);
  });
});

function adicionarAoCarrinho(prod) {
  const existente = carrinho.find((item) => item.id === prod.id);
  if (existente) {
    existente.qtd += 1;
  } else {
    carrinho.push({ id: prod.id, nome: prod.nome, preco: prod.preco, qtd: 1 });
  }
  $("loja-aviso").textContent = `"${prod.nome}" adicionado ao carrinho!`;
  atualizarCarrinhoUI();
}

function atualizarCarrinhoUI() {
  const totalQtd = carrinho.reduce((acc, item) => acc + item.qtd, 0);
  const totalValor = carrinho.reduce((acc, item) => acc + item.preco * item.qtd, 0);

  $("carrinho-qtd").textContent = totalQtd;
  $("carrinho-total").textContent = formatarMoeda(totalValor);

  if (carrinho.length === 0) {
    $("carrinho-itens-texto").textContent = "Nenhum item adicionado ainda.";
  } else {
    $("carrinho-itens-texto").textContent = carrinho
      .map((i) => `${i.qtd}x ${i.nome} (${formatarMoeda(i.preco * i.qtd)})`)
      .join(" · ");
  }
}

$("btn-limpar-carrinho").addEventListener("click", () => {
  carrinho = [];
  $("loja-aviso").textContent = "";
  atualizarCarrinhoUI();
});

$("btn-finalizar-compra").addEventListener("click", async () => {
  if (carrinho.length === 0) {
    $("loja-aviso").textContent = "Adicione pelo menos um item ao carrinho antes de finalizar.";
    return;
  }

  if (!usuario) {
    avisoLogin = "Faça login para concluir sua compra na loja.";
    location.hash = "#entrar";
    atualizarInterfaceLogin();
    return;
  }

  const valorTotal = carrinho.reduce((acc, item) => acc + item.preco * item.qtd, 0);

  try {
    const resposta = await fetch("/api/comprar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ itens: carrinho, valor_total: valorTotal })
    });
    const dados = await resposta.json();

    if (resposta.ok && dados.sucesso) {
      carrinho = [];
      atualizarCarrinhoUI();
      $("loja-aviso").textContent = "Compra realizada com sucesso! Veja seu pedido em Minha Conta.";
    } else {
      $("loja-aviso").textContent = dados.erro || "Erro ao finalizar compra.";
    }
  } catch (erro) {
    $("loja-aviso").textContent = "Erro de conexão ao finalizar compra.";
  }
});

/* ==========================================================
   5. AUTENTICAÇÃO E PAINÉIS (CLIENTE E ADMIN)
   ========================================================== */
function atualizarInterfaceLogin() {
  const logado = usuario !== null;
  const isAdmin = logado && usuario.tipo === "admin";

  $("box-login").hidden = logado;
  $("area-cliente").hidden = !logado || isAdmin;
  $("area-admin").hidden = !isAdmin;

  $("login-texto").textContent = avisoLogin || "Acesse sua conta ou cadastre-se automaticamente para adotar e comprar.";
  $("aba-entrar").textContent = logado ? (isAdmin ? "Painel Admin" : "Minha conta") : "Entrar";

  if (logado && !isAdmin) {
    $("cliente-boas-vindas").textContent = `Olá, ${usuario.email}!`;
  }
}

async function carregarDadosPainel() {
  if (!usuario) return;

  if (usuario.tipo === "admin") {
    const res = await fetch("/api/admin/painel");
    if (!res.ok) return;
    const dados = await res.json();
    renderizarPainelAdmin(dados);
  } else {
    const res = await fetch("/api/cliente/painel");
    if (!res.ok) return;
    const dados = await res.json();
    renderizarPainelCliente(dados);
  }
}

function renderizarPainelCliente(dados) {
  const listaAdocoes = $("cliente-lista-adocoes");
  listaAdocoes.innerHTML = "";

  if (dados.adocoes.length === 0) {
    listaAdocoes.innerHTML = "<p class='subtitulo'>Você ainda não adotou nenhum pet.</p>";
  } else {
    dados.adocoes.forEach((a) => {
      const card = document.createElement("article");
      card.className = "pet";
      card.innerHTML = `
        <img src="${a.pet_foto}" alt="${a.pet_nome}">
        <div class="pet-corpo">
          <h3>${a.pet_nome}</h3>
          <div class="etiquetas"><span>Adotado em ${a.data}</span></div>
          <p><b>Como está:</b> ${a.status_pet}</p>
          <p><b>Endereço cadastrado:</b> ${a.endereco}</p>
        </div>
      `;
      listaAdocoes.appendChild(card);
    });
  }

  const listaCompras = $("cliente-lista-compras");
  listaCompras.innerHTML = "";

  if (dados.compras.length === 0) {
    listaCompras.innerHTML = "<p class='subtitulo'>Nenhuma compra realizada na loja ainda.</p>";
  } else {
    dados.compras.forEach((c) => {
      const card = document.createElement("div");
      card.className = "cartao";
      card.innerHTML = `
        <h3>Pedido #${c.id} · ${c.data}</h3>
        <p style="margin: 8px 0;">${c.itens_resumo}</p>
        <b class="preco-destaque">${formatarMoeda(c.valor_total)}</b>
      `;
      listaCompras.appendChild(card);
    });
  }
}

function renderizarPainelAdmin(dados) {
  // 1. Gráfico visual de barras
  const g = dados.grafico;
  const totalGeral = Math.max(g.total_adocoes + g.pets_disponiveis, 1);
  const pctAdotados = Math.round((g.total_adocoes / totalGeral) * 100);
  const pctCaes = g.total_adocoes ? Math.round((g.caes_adotados / g.total_adocoes) * 100) : 0;
  const pctGatos = g.total_adocoes ? Math.round((g.gatos_adotados / g.total_adocoes) * 100) : 0;

  $("admin-grafico").innerHTML = `
    <div class="barra-grafico-item">
      <div class="barra-grafico-topo"><span>Total de Adoções Realizadas</span><span>${g.total_adocoes} de ${g.total_adocoes + g.pets_disponiveis} pets (${pctAdotados}%)</span></div>
      <div class="barra-grafico-trilha"><div class="barra-grafico-preenchimento" style="width: ${pctAdotados}%"></div></div>
    </div>
    <div class="barra-grafico-item">
      <div class="barra-grafico-topo"><span>Cães Adotados</span><span>${g.caes_adotados} (${pctCaes}%)</span></div>
      <div class="barra-grafico-trilha"><div class="barra-grafico-preenchimento" style="width: ${pctCaes}%"></div></div>
    </div>
    <div class="barra-grafico-item">
      <div class="barra-grafico-topo"><span>Gatos Adotados</span><span>${g.gatos_adotados} (${pctGatos}%)</span></div>
      <div class="barra-grafico-trilha"><div class="barra-grafico-preenchimento" style="width: ${pctGatos}%"></div></div>
    </div>
  `;

  // 2. Adoções e atualização de status do pet
  const listaAdocoes = $("admin-lista-adocoes");
  listaAdocoes.innerHTML = "";

  if (dados.adocoes.length === 0) {
    listaAdocoes.innerHTML = "<p class='subtitulo'>Nenhuma adoção registrada até o momento.</p>";
  } else {
    dados.adocoes.forEach((a) => {
      const card = document.createElement("div");
      card.className = "cartao";
      card.innerHTML = `
        <h3>🐾 ${a.pet_nome}</h3>
        <p><b>Adotante:</b> ${a.cliente_email} (${a.data})</p>
        <p><b>Endereço:</b> ${a.endereco}</p>
        <p><b>Vacinas:</b> ${a.vacinas}</p>
        <div style="margin-top: 12px; display: grid; gap: 8px;">
          <input class="input-inline" type="text" id="status-input-${a.id}" value="${a.status_pet}">
          <button class="botao" type="button" onclick="salvarStatusPet(${a.id})">Atualizar status do pet</button>
        </div>
      `;
      listaAdocoes.appendChild(card);
    });
  }

  // 3. Compras realizadas
  const listaCompras = $("admin-lista-compras");
  listaCompras.innerHTML = "";

  if (dados.compras.length === 0) {
    listaCompras.innerHTML = "<p class='subtitulo'>Nenhuma venda registrada na loja ainda.</p>";
  } else {
    dados.compras.forEach((c) => {
      const card = document.createElement("div");
      card.className = "cartao";
      card.innerHTML = `
        <h3>🛍️ Pedido #${c.id}</h3>
        <p><b>Cliente:</b> ${c.cliente_email} (${c.data})</p>
        <p style="margin: 6px 0;">${c.itens_resumo}</p>
        <b class="preco-destaque">${formatarMoeda(c.valor_total)}</b>
      `;
      listaCompras.appendChild(card);
    });
  }
}

window.salvarStatusPet = async function (adocaoId) {
  const input = $(`status-input-${adocaoId}`);
  const status_pet = input.value.trim();
  if (!status_pet) return;

  const res = await fetch("/api/admin/status-pet", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ adocao_id: adocaoId, status_pet })
  });
  if (res.ok) {
    alert("Status de acompanhamento do pet atualizado!");
  }
};

async function verificarSessaoAtual() {
  try {
    const resposta = await fetch("/api/sessao");
    const dados = await resposta.json();
    usuario = dados.logado ? { email: dados.email, tipo: dados.tipo } : null;
    atualizarInterfaceLogin();
    if (usuario && location.hash === "#entrar") {
      carregarDadosPainel();
    }
  } catch (erro) {
    console.error("Erro ao verificar sessão:", erro);
  }
}

$("form-login").addEventListener("submit", async (e) => {
  e.preventDefault();
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
    usuario = { email: dados.email, tipo: dados.tipo };
    $("form-login").reset();
    atualizarInterfaceLogin();
    carregarDadosPainel();
  } catch (erro) {
    $("erro").textContent = "Erro de conexão com o servidor.";
  }
});

async function fazerLogout() {
  await fetch("/api/logout", { method: "POST" });
  usuario = null;
  atualizarInterfaceLogin();
}

$("sair-cliente").addEventListener("click", fazerLogout);
$("sair-admin").addEventListener("click", fazerLogout);

/* ==========================================================
   6. INICIALIZAÇÃO
   ========================================================== */
carregarPets();
carregarProdutos();
verificarSessaoAtual();
mostrarAba();
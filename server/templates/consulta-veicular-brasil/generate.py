#!/usr/bin/env python3
"""Gera o template ToolJet "Consulta veicular Brasil" (appV2 definition.json + manifest.json)."""
import json
import uuid
import os

NS = uuid.UUID("7c9e6679-7425-40de-944b-e07fc1f90ae7")


def uid(name: str) -> str:
    return str(uuid.uuid5(NS, "consulta-veicular-brasil/" + name))


TS = "2026-08-16T12:00:00.000Z"
ORG_ID = uid("org")
USER_ID = uid("user")
APP_ID = uid("app")
VERSION_ID = uid("app-version-v1")
PAGE_ID = uid("page-home")
ENV_DEV = uid("env-development")
ENV_STG = uid("env-staging")
ENV_PROD = uid("env-production")
DS_RESTAPI = uid("ds-restapi")
DS_RUNJS = uid("ds-runjs")

Q_ORQUESTRADOR = uid("q-executarConsulta")
Q_PROVEDOR = uid("q-consultaProvedor")
Q_DEMO = uid("q-consultaDemo")
Q_FIPE = uid("q-consultarFipe")

# ---------------------------------------------------------------------------
# Códigos JavaScript das queries
# ---------------------------------------------------------------------------

CODE_ORQUESTRADOR = r"""// Orquestra a consulta veicular: valida a entrada, decide entre chassi e
// Renavam, escolhe o modo (provedor real ou demonstração) e consolida o
// resultado no formato canônico usado por toda a interface.
const bruto = components.inputIdentificador.value || '';
const entrada = bruto.toUpperCase().replace(/[^A-Z0-9]/g, '');

await actions.setVariable('erroConsulta', '');
await actions.setVariable('resultado', null);

const somenteDigitos = /^[0-9]+$/.test(entrada);
let tipo = null;
if (entrada.length === 17 && /^[A-HJ-NPR-Z0-9]{17}$/.test(entrada)) {
  tipo = 'chassi';
} else if (somenteDigitos && entrada.length >= 9 && entrada.length <= 11) {
  tipo = 'renavam';
}

if (!tipo) {
  await actions.setVariable(
    'erroConsulta',
    'Identificador inválido. Informe um chassi com 17 caracteres (sem as letras I, O e Q) ou um Renavam com 9 a 11 dígitos.'
  );
  return null;
}

await actions.setVariable('tipoConsulta', tipo);
await actions.setVariable('identificadorConsulta', entrada);

const apiConfigurada =
  typeof constants !== 'undefined' &&
  constants &&
  constants.CONSULTA_VEICULAR_API_URL &&
  String(constants.CONSULTA_VEICULAR_API_URL).indexOf('http') === 0;
await actions.setVariable('modoDemo', !apiConfigurada);

let resultado = null;
try {
  if (apiConfigurada) {
    await queries.consultaProvedor.run();
    resultado = queries.consultaProvedor.getData();
  } else {
    await queries.consultaDemo.run({ identificador: entrada, tipo: tipo });
    resultado = queries.consultaDemo.getData();
  }
} catch (erro) {
  await actions.setVariable(
    'erroConsulta',
    'Falha ao consultar o veículo: ' + ((erro && erro.message) || erro)
  );
  return null;
}

if (!resultado || !resultado.veiculo) {
  await actions.setVariable(
    'erroConsulta',
    'A consulta não retornou dados para o identificador informado. Verifique o número e tente novamente.'
  );
  return null;
}

// Enriquecimento opcional: consulta o valor vigente na tabela FIPE (API
// pública Parallelum) quando o provedor devolve o código FIPE do veículo.
if (apiConfigurada && resultado.veiculo.codigoFipe && resultado.veiculo.anoModelo) {
  try {
    await actions.setVariable('fipeParams', {
      codigo: String(resultado.veiculo.codigoFipe).trim(),
      anoCodigo:
        String(resultado.veiculo.anoModelo) + '-' + (resultado.veiculo.codigoCombustivel || 1),
    });
    await queries.consultarFipe.run();
    const fipeAoVivo = queries.consultarFipe.getData();
    if (fipeAoVivo && fipeAoVivo.valor) {
      resultado.fipe = Object.assign({}, resultado.fipe || {}, fipeAoVivo);
    }
  } catch (erro) {
    // A consulta FIPE é complementar; mantém o valor informado pelo provedor.
  }
}

await actions.setVariable('resultado', resultado);
return resultado;
"""

CODE_DEMO = r"""// Modo demonstração: gera um laudo veicular simulado e determinístico a
// partir do identificador informado, seguindo o mesmo contrato de dados do
// provedor real. Permite explorar o app sem contratar uma API paga.
const id = (parameters && parameters.identificador) || variables.identificadorConsulta || '9BWZZZ377VT004251';
const tipo = (parameters && parameters.tipo) || variables.tipoConsulta || 'chassi';

let h = 7;
for (let i = 0; i < id.length; i++) {
  h = ((h * 31 + id.charCodeAt(i)) & 0x7fffffff) >>> 0;
}
const pick = (arr, salto) => arr[Math.floor(h / (salto + 1)) % arr.length];

const catalogo = [
  { marca: 'Volkswagen', modelo: 'T-Cross 1.4 TSI Highline', codigoFipe: '005526-3', combustivel: 'Gasolina', valorBase: 128500 },
  { marca: 'Fiat', modelo: 'Argo Drive 1.3 Firefly', codigoFipe: '001513-5', combustivel: 'Flex', valorBase: 78900 },
  { marca: 'Chevrolet', modelo: 'Onix Plus Premier 1.0 Turbo', codigoFipe: '004496-3', combustivel: 'Flex', valorBase: 96400 },
  { marca: 'Toyota', modelo: 'Corolla XEi 2.0', codigoFipe: '002110-0', combustivel: 'Flex', valorBase: 142300 },
  { marca: 'Hyundai', modelo: 'HB20 Comfort 1.0 TGDI', codigoFipe: '015324-9', combustivel: 'Flex', valorBase: 84700 },
  { marca: 'Jeep', modelo: 'Compass Longitude T270', codigoFipe: '017105-0', combustivel: 'Flex', valorBase: 165800 },
];
const cores = ['Prata', 'Preto', 'Branco', 'Cinza', 'Vermelho', 'Azul'];
const locais = [
  { municipio: 'São Paulo', uf: 'SP' },
  { municipio: 'Belo Horizonte', uf: 'MG' },
  { municipio: 'Curitiba', uf: 'PR' },
  { municipio: 'Rio de Janeiro', uf: 'RJ' },
  { municipio: 'Porto Alegre', uf: 'RS' },
  { municipio: 'Salvador', uf: 'BA' },
];

const item = pick(catalogo, 3);
const cor = pick(cores, 5);
const local = pick(locais, 7);
const anoFabricacao = 2015 + (h % 10);
const anoModelo = anoFabricacao + (h % 2);

const temGravame = h % 3 === 0;
const temSinistro = h % 4 === 0;
const temLeilao = h % 5 === 0;
const temRestricaoJudicial = h % 9 === 0;
const rouboFurto = h % 13 === 0;
const idadeVeiculo = Math.max(1, 2026 - anoModelo);
const brl = (n) => n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

// Depreciação simples de 7% ao ano sobre o valor base do catálogo.
const valorAtual = Math.round(item.valorBase * Math.pow(0.93, idadeVeiculo));

const meses = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
const agora = new Date();
const historico = [];
for (let i = 11; i >= 0; i--) {
  const d = new Date(agora.getFullYear(), agora.getMonth() - i, 1);
  const oscilacao = 1 + (((h >> (i % 16)) % 7) - 3) / 100;
  historico.push({
    mes: meses[d.getMonth()] + ' de ' + d.getFullYear(),
    valor: brl(Math.round(valorAtual * Math.pow(0.994, i) * oscilacao)),
  });
}

const restricoes = [];
if (temGravame) {
  restricoes.push({
    tipo: 'Alienação fiduciária',
    descricao: 'Veículo financiado com gravame ativo registrado no SNG.',
    orgao: 'Banco Demo S.A.',
  });
}
if (temRestricaoJudicial) {
  restricoes.push({
    tipo: 'RENAJUD',
    descricao: 'Restrição judicial de transferência inserida via sistema RENAJUD.',
    orgao: 'TJ' + local.uf,
  });
}
if (rouboFurto) {
  restricoes.push({
    tipo: 'Roubo/Furto',
    descricao: 'Registro de ocorrência de roubo ou furto vigente na base nacional.',
    orgao: 'SSP-' + local.uf,
  });
}

const sinistros = temSinistro
  ? [
      {
        data: '14/03/' + (anoModelo + 2),
        tipo: pick(['Colisão', 'Enchente/alagamento', 'Incêndio', 'Capotamento'], 11),
        gravidade: pick(['Pequena monta', 'Média monta', 'Grande monta'], 13),
        uf: local.uf,
        descricao: 'Sinistro indenizado registrado por seguradora no período de vigência da apólice.',
      },
    ]
  : [];

const leiloes = temLeilao
  ? [
      {
        data: '09/08/' + (anoModelo + 3),
        leiloeiro: 'Leilões Demo Ltda.',
        comitente: 'Seguradora Demo S.A.',
        lote: String(1000 + (h % 900)),
        condicao: pick(['Batido', 'Sucata aproveitável', 'Conservado', 'Sinistrado com recuperação'], 17),
        notaAvaliacao: String(1 + (h % 5)) + ' / 5',
      },
    ]
  : [];

const status = rouboFurto || temRestricaoJudicial ? 'Alerta' : restricoes.length > 0 ? 'Com restrições' : 'Regular';

const digitos = String(h).padStart(11, '3').slice(0, 11);
const chassi = tipo === 'chassi' ? id : '9BW' + digitos.slice(0, 6) + 'T' + digitos.slice(4, 11);
const renavam = tipo === 'renavam' ? id : digitos;

return {
  veiculo: {
    chassi: chassi,
    renavam: renavam,
    placa: pick(['ABC', 'BRA', 'RIO', 'SPX', 'MGV'], 19) + digitos.slice(2, 3) + pick(['A', 'B', 'C', 'D', 'E'], 23) + digitos.slice(5, 7),
    marca: item.marca,
    modelo: item.modelo,
    anoFabricacao: anoFabricacao,
    anoModelo: anoModelo,
    cor: cor,
    combustivel: item.combustivel,
    municipio: local.municipio,
    uf: local.uf,
    codigoFipe: item.codigoFipe,
    procedencia: 'Nacional',
    tipo: 'Automóvel',
    situacao: status === 'Regular' ? 'Em circulação' : 'Em circulação com apontamentos',
  },
  situacaoLegal: {
    status: status,
    rouboFurto: {
      indicador: rouboFurto,
      detalhes: rouboFurto
        ? 'Constam registros de roubo ou furto para este veículo.'
        : 'Nada consta na base nacional de roubos e furtos.',
    },
    gravame: {
      status: temGravame ? 'Ativo' : 'Sem gravame',
      financeira: temGravame ? 'Banco Demo S.A.' : null,
      dataInclusao: temGravame ? '02/05/' + (anoModelo + 1) : null,
    },
    debitos: {
      ipva: h % 6 === 0 ? brl(800 + (h % 1400)) : 'Sem débitos',
      licenciamento: h % 7 === 0 ? brl(160) : 'Em dia',
      multas: h % 5 === 0 ? brl(190 + (h % 900)) : 'Sem multas',
    },
    renajud: temRestricaoJudicial
      ? 'Constam restrições judiciais ativas (RENAJUD).'
      : 'Nada consta no RENAJUD.',
    restricoes: restricoes,
  },
  sinistros: {
    indicador: temSinistro,
    ocorrencias: sinistros,
  },
  leiloes: {
    indicador: temLeilao,
    ocorrencias: leiloes,
  },
  fipe: {
    codigoFipe: item.codigoFipe,
    valor: brl(valorAtual),
    mesReferencia: meses[agora.getMonth()] + ' de ' + agora.getFullYear(),
    historico: historico,
  },
  metadados: {
    fonte: 'Dados simulados — modo demonstração',
    modoDemo: true,
    consultadoEm: agora.toLocaleString('pt-BR'),
  },
};
"""

TRANSFORM_PROVEDOR = r"""// Normaliza a resposta do provedor de consulta veicular para o contrato
// canônico do app. Ajuste os campos abaixo conforme o provedor contratado
// (Infosimples, API Brasil, Checkpro, Olho no Carro etc.).
const raiz = (data && (data.dados || data.data || data.resultado || data.response)) || data || {};
const v = raiz.veiculo || raiz.dadosVeiculo || raiz;
const legal = raiz.situacaoLegal || raiz.situacao_legal || raiz.restricoes || {};
const sin = raiz.sinistros || raiz.sinistro || {};
const lei = raiz.leiloes || raiz.leilao || {};
const fipe = raiz.fipe || raiz.tabelaFipe || {};

const texto = (valor, padrao) => {
  if (valor === undefined || valor === null || valor === '') return padrao;
  return String(valor);
};
const lista = (valor) => (Array.isArray(valor) ? valor : []);

const restricoes = lista(legal.restricoes || raiz.listaRestricoes).map((r) => ({
  tipo: texto(r.tipo || r.nome || r.restricao, 'Restrição'),
  descricao: texto(r.descricao || r.detalhe || r.observacao, '—'),
  orgao: texto(r.orgao || r.origem, '—'),
}));

const ocorrenciasSinistro = lista(sin.ocorrencias || sin.registros).map((s) => ({
  data: texto(s.data || s.dataOcorrencia, '—'),
  tipo: texto(s.tipo || s.natureza, '—'),
  gravidade: texto(s.gravidade || s.monta, '—'),
  uf: texto(s.uf || s.estado, '—'),
  descricao: texto(s.descricao || s.detalhe, '—'),
}));

const ocorrenciasLeilao = lista(lei.ocorrencias || lei.registros).map((l) => ({
  data: texto(l.data || l.dataLeilao, '—'),
  leiloeiro: texto(l.leiloeiro, '—'),
  comitente: texto(l.comitente || l.seguradora, '—'),
  lote: texto(l.lote, '—'),
  condicao: texto(l.condicao || l.condicaoGeral || l.situacao, '—'),
  notaAvaliacao: texto(l.notaAvaliacao || l.nota, '—'),
}));

const indicadorSinistro = sin.indicador !== undefined ? !!sin.indicador : ocorrenciasSinistro.length > 0;
const indicadorLeilao = lei.indicador !== undefined ? !!lei.indicador : ocorrenciasLeilao.length > 0;
const temAlerta = !!(legal.rouboFurto && (legal.rouboFurto.indicador || legal.rouboFurto === true));

return {
  veiculo: {
    chassi: texto(v.chassi || v.vin, variables.tipoConsulta === 'chassi' ? variables.identificadorConsulta : '—'),
    renavam: texto(v.renavam, variables.tipoConsulta === 'renavam' ? variables.identificadorConsulta : '—'),
    placa: texto(v.placa, '—'),
    marca: texto(v.marca || v.fabricante, '—'),
    modelo: texto(v.modelo || v.versao, '—'),
    anoFabricacao: texto(v.anoFabricacao || v.ano_fabricacao, '—'),
    anoModelo: texto(v.anoModelo || v.ano_modelo || v.ano, ''),
    cor: texto(v.cor, '—'),
    combustivel: texto(v.combustivel, '—'),
    codigoCombustivel: v.codigoCombustivel || v.codigo_combustivel || null,
    municipio: texto(v.municipio || v.cidade, '—'),
    uf: texto(v.uf || v.estado, '—'),
    codigoFipe: texto(v.codigoFipe || v.codigo_fipe || fipe.codigoFipe || fipe.codigo, ''),
    procedencia: texto(v.procedencia, '—'),
    tipo: texto(v.tipo || v.tipoVeiculo, '—'),
    situacao: texto(v.situacao || legal.situacao, '—'),
  },
  situacaoLegal: {
    status: texto(legal.status, temAlerta ? 'Alerta' : restricoes.length > 0 ? 'Com restrições' : 'Regular'),
    rouboFurto: {
      indicador: temAlerta,
      detalhes: texto(
        legal.rouboFurto && legal.rouboFurto.detalhes,
        temAlerta ? 'Constam registros de roubo ou furto.' : 'Nada consta na base de roubos e furtos.'
      ),
    },
    gravame: {
      status: texto(legal.gravame && legal.gravame.status, 'Não informado'),
      financeira: (legal.gravame && legal.gravame.financeira) || null,
      dataInclusao: (legal.gravame && legal.gravame.dataInclusao) || null,
    },
    debitos: {
      ipva: texto(legal.debitos && legal.debitos.ipva, 'Não informado'),
      licenciamento: texto(legal.debitos && legal.debitos.licenciamento, 'Não informado'),
      multas: texto(legal.debitos && legal.debitos.multas, 'Não informado'),
    },
    renajud: texto(legal.renajud, 'Não informado'),
    restricoes: restricoes,
  },
  sinistros: { indicador: indicadorSinistro, ocorrencias: ocorrenciasSinistro },
  leiloes: { indicador: indicadorLeilao, ocorrencias: ocorrenciasLeilao },
  fipe: {
    codigoFipe: texto(fipe.codigoFipe || fipe.codigo, ''),
    valor: texto(fipe.valor || fipe.valorAtual, ''),
    mesReferencia: texto(fipe.mesReferencia || fipe.referencia, ''),
    historico: lista(fipe.historico).map((hst) => ({
      mes: texto(hst.mes || hst.mesReferencia, '—'),
      valor: texto(hst.valor, '—'),
    })),
  },
  metadados: {
    fonte: texto(raiz.fonte || (raiz.metadados && raiz.metadados.fonte), 'Provedor de consulta veicular'),
    modoDemo: false,
    consultadoEm: new Date().toLocaleString('pt-BR'),
  },
};
"""

TRANSFORM_FIPE = r"""// Normaliza a resposta da API pública da FIPE (Parallelum, v2).
if (!data || !data.price) {
  return null;
}
return {
  codigoFipe: data.codeFipe,
  valor: data.price,
  mesReferencia: data.referenceMonth,
  marca: data.brand,
  modelo: data.model,
  anoModelo: data.modelYear,
  combustivel: data.fuel,
};
"""

# ---------------------------------------------------------------------------
# Helpers de montagem
# ---------------------------------------------------------------------------

CARREGANDO = "{{queries.executarConsulta.isLoading || queries.consultaProvedor.isLoading || queries.consultaDemo.isLoading}}"
TEM_RESULTADO = "{{!!variables.resultado}}"
R = "variables.resultado"


def layout(comp_id, name, desktop, mobile=None):
    d_left, d_top, d_w, d_h = desktop
    m_left, m_top, m_w, m_h = mobile if mobile else desktop
    return [
        {
            "id": uid("layout-desktop-" + name),
            "type": "desktop",
            "top": d_top,
            "left": d_left,
            "width": d_w,
            "height": d_h,
            "componentId": comp_id,
            "dimensionUnit": "count",
            "updatedAt": TS,
        },
        {
            "id": uid("layout-mobile-" + name),
            "type": "mobile",
            "top": m_top,
            "left": m_left,
            "width": m_w,
            "height": m_h,
            "componentId": comp_id,
            "dimensionUnit": "count",
            "updatedAt": TS,
        },
    ]


def component(name, ctype, desktop, mobile=None, parent=None, properties=None, styles=None, validation=None):
    cid = uid("component-" + name)
    return {
        "id": cid,
        "name": name,
        "type": ctype,
        "pageId": PAGE_ID,
        "parent": parent,
        "properties": properties or {},
        "general": {},
        "styles": styles or {},
        "generalStyles": {"boxShadow": {"value": "0px 0px 0px 0px #00000040"}},
        "displayPreferences": {
            "showOnDesktop": {"value": "{{true}}"},
            "showOnMobile": {"value": "{{true}}"},
        },
        "validation": validation or {},
        "createdAt": TS,
        "updatedAt": TS,
        "layouts": layout(cid, name, desktop, mobile),
    }


def texto_html(name, html, desktop, mobile=None, parent=None, visibility="{{true}}", extra_styles=None):
    styles = {
        "backgroundColor": {"value": "#ffffff00"},
        "textColor": {"value": "#1b1f31"},
        "textSize": {"value": "14"},
        "textAlign": {"value": "left"},
        "fontWeight": {"value": "normal"},
        "decoration": {"value": "none"},
        "transformation": {"value": "none"},
        "fontStyle": {"value": "normal"},
    }
    if extra_styles:
        styles.update(extra_styles)
    return component(
        name,
        "Text",
        desktop,
        mobile,
        parent=parent,
        properties={
            "text": {"value": html},
            "textFormat": {"value": "html"},
            "visibility": {"value": visibility},
            "loadingState": {"value": "{{false}}"},
            "disabledState": {"value": "{{false}}"},
        },
        styles=styles,
    )


def tabela(name, data_expr, columns, desktop, parent=None, mobile=None):
    cols = []
    for i, (col_name, key) in enumerate(columns):
        cols.append(
            {
                "id": uid("col-" + name + "-" + key),
                "name": col_name,
                "key": key,
                "columnType": "string",
                "isEditable": "{{false}}",
                "fxActiveFields": [],
            }
        )
    return component(
        name,
        "Table",
        desktop,
        mobile,
        parent=parent,
        properties={
            "title": {"value": "Table"},
            "data": {"value": data_expr},
            "columns": {"value": cols},
            "useDynamicColumn": {"value": "{{false}}"},
            "autogenerateColumns": {"value": False},
            "visible": {"value": "{{true}}"},
            "visibility": {"value": "{{true}}"},
            "loadingState": {"value": CARREGANDO},
            "rowsPerPage": {"value": "{{10}}"},
            "enablePagination": {"value": "{{true}}"},
            "serverSidePagination": {"value": "{{false}}"},
            "displaySearchBox": {"value": "{{false}}"},
            "showFilterButton": {"value": "{{false}}"},
            "showDownloadButton": {"value": "{{true}}"},
            "showBulkUpdateActions": {"value": "{{false}}"},
            "showBulkSelector": {"value": "{{false}}"},
            "highlightSelectedRow": {"value": "{{false}}"},
            "allowSelection": {"value": "{{false}}"},
            "hideColumnSelectorButton": {"value": "{{true}}"},
            "showAddNewRowButton": {"value": "{{false}}"},
            "enabledSort": {"value": "{{true}}"},
            "columnSizes": {"value": {}},
            "actions": {"value": []},
            "disabledState": {"value": "{{false}}"},
        },
        styles={
            "borderRadius": {"value": "8"},
            "tableType": {"value": "table-classic"},
            "cellSize": {"value": "regular"},
            "contentWrap": {"value": "{{true}}"},
            "columnHeaderWrap": {"value": "fixed"},
        },
    )


def card(name, titulo, valor_expr, desktop, cor_valor="#1b1f31", subtitulo_expr=None):
    sub = (
        f"<div style='margin-top:4px;font-size:12px;color:#687076'>{subtitulo_expr}</div>"
        if subtitulo_expr
        else ""
    )
    html = (
        "<div style='background:#ffffff;border:1px solid #e6e8eb;border-radius:10px;"
        "padding:14px 16px;height:100%;box-sizing:border-box'>"
        f"<div style='font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#687076'>{titulo}</div>"
        f"<div style='margin-top:6px;font-size:18px;font-weight:700;color:{cor_valor};line-height:1.25'>{valor_expr}</div>"
        f"{sub}</div>"
    )
    return texto_html(name, html, desktop, visibility=TEM_RESULTADO)


# ---------------------------------------------------------------------------
# Componentes
# ---------------------------------------------------------------------------

components = []

components.append(
    texto_html(
        "tituloApp",
        "<div style='padding-top:6px'>"
        "<div style='font-size:26px;font-weight:800;color:#1b1f31'>🚗 Consulta Veicular Brasil</div>"
        "<div style='margin-top:4px;font-size:14px;color:#687076'>"
        "Situação legal, sinistros, leilões e valor de referência FIPE a partir do chassi ou do Renavam."
        "</div></div>",
        (1, 20, 41, 80),
        (1, 10, 41, 90),
    )
)

components.append(
    component(
        "inputIdentificador",
        "TextInput",
        (1, 110, 22, 40),
        (1, 110, 41, 40),
        properties={
            "value": {"value": ""},
            "label": {"value": ""},
            "placeholder": {"value": "Chassi (17 caracteres) ou Renavam (9 a 11 dígitos)"},
            "visibility": {"value": "{{true}}"},
            "disabledState": {"value": "{{false}}"},
            "loadingState": {"value": "{{false}}"},
            "tooltip": {"value": "Prefira o chassi: identifica o veículo de forma única em todas as bases."},
        },
        styles={
            "borderRadius": {"value": "8"},
            "visibility": {"value": "{{true}}"},
            "disabledState": {"value": "{{false}}"},
        },
        validation={
            "mandatory": {"value": "{{false}}"},
            "regex": {"value": ""},
            "minLength": {"value": ""},
            "maxLength": {"value": ""},
            "customRule": {"value": ""},
        },
    )
)

components.append(
    component(
        "botaoConsultar",
        "Button",
        (24, 110, 7, 40),
        (1, 155, 20, 40),
        properties={
            "text": {"value": "Consultar"},
            "loadingState": {"value": CARREGANDO, "fxActive": True},
            "visibility": {"value": "{{true}}"},
            "disabledState": {"value": "{{false}}"},
            "tooltip": {"value": ""},
        },
        styles={
            "backgroundColor": {"value": "#3e63ddff"},
            "textColor": {"value": "#FFFFFF"},
            "borderRadius": {"value": "{{8}}"},
            "borderColor": {"value": "#ffffff00"},
            "loaderColor": {"value": "#FFFFFF"},
            "padding": {"value": "default"},
        },
    )
)

DETECTA = (
    "{{(() => { const e = (components.inputIdentificador.value || '').toUpperCase().replace(/[^A-Z0-9]/g, ''); "
    "if (!e) return ''; "
    "if (e.length === 17 && /^[A-HJ-NPR-Z0-9]{17}$/.test(e)) return '✔ Chassi detectado'; "
    "if (/^[0-9]{9,11}$/.test(e)) return '✔ Renavam detectado'; "
    "return '… identificador incompleto'; })()}}"
)
components.append(
    texto_html(
        "textoTipoDetectado",
        f"<div style='padding-top:10px;font-size:13px;color:#687076'>{DETECTA}</div>",
        (32, 110, 10, 40),
        (22, 155, 20, 40),
    )
)

components.append(
    texto_html(
        "textoErro",
        "<div style='background:#fef3f2;border:1px solid #fda29b;border-radius:8px;padding:10px 14px;"
        "color:#b42318;font-size:13px'>⚠️ {{variables.erroConsulta}}</div>",
        (1, 158, 41, 40),
        (1, 205, 41, 50),
        visibility="{{!!variables.erroConsulta}}",
    )
)

components.append(
    texto_html(
        "bannerDemo",
        "<div style='background:#fffaeb;border:1px solid #fec84b;border-radius:8px;padding:10px 14px;"
        "color:#93370d;font-size:13px'>🧪 <b>Modo demonstração:</b> os dados exibidos são simulados. "
        "Configure as constantes <code>CONSULTA_VEICULAR_API_URL</code> e "
        "<code>CONSULTA_VEICULAR_API_KEY</code> no workspace para consultar um provedor real.</div>",
        (1, 158, 41, 40),
        (1, 205, 41, 60),
        visibility="{{!variables.erroConsulta && variables.modoDemo === true && !!variables.resultado}}",
    )
)

components.append(
    texto_html(
        "estadoVazio",
        "<div style='background:#ffffff;border:1px dashed #c1c8cd;border-radius:12px;padding:28px;"
        "text-align:center;color:#687076'>"
        "<div style='font-size:34px'>🔎</div>"
        "<div style='margin-top:8px;font-size:16px;font-weight:600;color:#1b1f31'>Informe um chassi ou Renavam para começar</div>"
        "<div style='margin-top:6px;font-size:13px'>Exemplo de chassi: <code>9BWZZZ377VT004251</code> &nbsp;•&nbsp; "
        "Exemplo de Renavam: <code>12345678901</code></div>"
        "<div style='margin-top:6px;font-size:13px'>A consulta retorna dados cadastrais, situação legal, "
        "restrições, histórico de sinistros e leilões, além do valor de referência na tabela FIPE.</div></div>",
        (1, 210, 41, 140),
        (1, 260, 41, 160),
        visibility="{{!variables.resultado}}",
    )
)

# Cards de resumo -----------------------------------------------------------
VEICULO_EXPR = f"{{{{({R} && {R}.veiculo.marca) || '—'}}}} {{{{({R} && {R}.veiculo.modelo) || ''}}}}"
components.append(
    card(
        "cardVeiculo",
        "Veículo",
        VEICULO_EXPR,
        (1, 210, 13, 100),
        subtitulo_expr=f"Placa {{{{({R} && {R}.veiculo.placa) || '—'}}}} • {{{{({R} && {R}.veiculo.municipio) || '—'}}}}/{{{{({R} && {R}.veiculo.uf) || '—'}}}}",
    )
)
components.append(
    card(
        "cardAno",
        "Ano / Cor / Combustível",
        f"{{{{({R} && {R}.veiculo.anoFabricacao) || '—'}}}}/{{{{({R} && {R}.veiculo.anoModelo) || '—'}}}}",
        (15, 210, 9, 100),
        subtitulo_expr=f"{{{{({R} && {R}.veiculo.cor) || '—'}}}} • {{{{({R} && {R}.veiculo.combustivel) || '—'}}}}",
    )
)
STATUS_COR = (
    f"{{{{({R} && {R}.situacaoLegal.status === 'Regular') ? '#12b76a' : "
    f"({R} && {R}.situacaoLegal.status === 'Com restrições') ? '#f79009' : '#f04438'}}}}"
)
components.append(
    card(
        "cardSituacao",
        "Situação legal",
        f"{{{{({R} && {R}.situacaoLegal.status) || '—'}}}}",
        (25, 210, 9, 100),
        cor_valor=STATUS_COR,
        subtitulo_expr=(
            f"{{{{({R} && {R}.sinistros.indicador) ? 'Com sinistro' : 'Sem sinistro'}}}} • "
            f"{{{{({R} && {R}.leiloes.indicador) ? 'Com leilão' : 'Sem leilão'}}}}"
        ),
    )
)
components.append(
    card(
        "cardFipe",
        "Valor FIPE",
        f"{{{{({R} && {R}.fipe.valor) || '—'}}}}",
        (35, 210, 7, 100),
        cor_valor="#3e63dd",
        subtitulo_expr=f"Ref. {{{{({R} && {R}.fipe.mesReferencia) || '—'}}}}",
    )
)

# Abas de resultado ---------------------------------------------------------
abas = component(
    "abasResultado",
    "Tabs",
    (1, 320, 41, 500),
    (1, 430, 41, 520),
    properties={
        "tabs": {
            "value": '{{[{"title":"Situação legal","id":"0"},{"title":"Sinistros","id":"1"},{"title":"Leilões","id":"2"},{"title":"Tabela FIPE","id":"3"}]}}'
        },
        "defaultTab": {"value": "0"},
        "hideTabs": {"value": "{{false}}"},
        "renderOnlyActiveTab": {"value": "{{true}}"},
        "visibility": {"value": TEM_RESULTADO},
    },
    styles={
        "highlightColor": {"value": "#3e63ddff"},
        "visibility": {"value": TEM_RESULTADO},
        "disabledState": {"value": "{{false}}"},
        "tabWidth": {"value": "auto"},
    },
)
components.append(abas)
TABS_ID = abas["id"]

KV = (
    "<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:10px'>"
    # Roubo e furto
    "<div style='background:#ffffff;border:1px solid #e6e8eb;border-radius:8px;padding:12px'>"
    "<div style='font-size:11px;text-transform:uppercase;color:#687076'>Roubo / Furto</div>"
    f"<div style='margin-top:4px;font-weight:700;color:{{{{({R} && {R}.situacaoLegal.rouboFurto.indicador) ? '#f04438' : '#12b76a'}}}}'>"
    f"{{{{({R} && {R}.situacaoLegal.rouboFurto.indicador) ? 'Consta ocorrência' : 'Nada consta'}}}}</div>"
    f"<div style='margin-top:4px;font-size:12px;color:#687076'>{{{{({R} && {R}.situacaoLegal.rouboFurto.detalhes) || ''}}}}</div></div>"
    # Gravame
    "<div style='background:#ffffff;border:1px solid #e6e8eb;border-radius:8px;padding:12px'>"
    "<div style='font-size:11px;text-transform:uppercase;color:#687076'>Gravame (SNG)</div>"
    f"<div style='margin-top:4px;font-weight:700;color:#1b1f31'>{{{{({R} && {R}.situacaoLegal.gravame.status) || '—'}}}}</div>"
    f"<div style='margin-top:4px;font-size:12px;color:#687076'>{{{{({R} && {R}.situacaoLegal.gravame.financeira) || 'Sem financeira vinculada'}}}}</div></div>"
    # RENAJUD
    "<div style='background:#ffffff;border:1px solid #e6e8eb;border-radius:8px;padding:12px'>"
    "<div style='font-size:11px;text-transform:uppercase;color:#687076'>RENAJUD</div>"
    f"<div style='margin-top:4px;font-size:13px;color:#1b1f31'>{{{{({R} && {R}.situacaoLegal.renajud) || '—'}}}}</div></div>"
    # Débitos
    "<div style='background:#ffffff;border:1px solid #e6e8eb;border-radius:8px;padding:12px'>"
    "<div style='font-size:11px;text-transform:uppercase;color:#687076'>IPVA</div>"
    f"<div style='margin-top:4px;font-weight:700;color:#1b1f31'>{{{{({R} && {R}.situacaoLegal.debitos.ipva) || '—'}}}}</div></div>"
    "<div style='background:#ffffff;border:1px solid #e6e8eb;border-radius:8px;padding:12px'>"
    "<div style='font-size:11px;text-transform:uppercase;color:#687076'>Licenciamento</div>"
    f"<div style='margin-top:4px;font-weight:700;color:#1b1f31'>{{{{({R} && {R}.situacaoLegal.debitos.licenciamento) || '—'}}}}</div></div>"
    "<div style='background:#ffffff;border:1px solid #e6e8eb;border-radius:8px;padding:12px'>"
    "<div style='font-size:11px;text-transform:uppercase;color:#687076'>Multas</div>"
    f"<div style='margin-top:4px;font-weight:700;color:#1b1f31'>{{{{({R} && {R}.situacaoLegal.debitos.multas) || '—'}}}}</div></div>"
    "</div>"
)
components.append(texto_html("resumoSituacaoLegal", KV, (1, 10, 39, 170), (1, 10, 39, 230), parent=f"{TABS_ID}-0"))
components.append(
    texto_html(
        "tituloRestricoes",
        "<div style='font-size:14px;font-weight:700;color:#1b1f31'>Restrições registradas "
        f"<span style='color:#687076;font-weight:400'>({{{{(({R} && {R}.situacaoLegal.restricoes) || []).length}}}})</span></div>",
        (1, 185, 39, 30),
        (1, 245, 39, 30),
        parent=f"{TABS_ID}-0",
    )
)
components.append(
    tabela(
        "tabelaRestricoes",
        f"{{{{(({R} && {R}.situacaoLegal.restricoes) || [])}}}}",
        [("Tipo", "tipo"), ("Descrição", "descricao"), ("Órgão", "orgao")],
        (1, 220, 39, 250),
        parent=f"{TABS_ID}-0",
        mobile=(1, 280, 39, 220),
    )
)

components.append(
    texto_html(
        "indicadorSinistros",
        f"<div style='background:{{{{({R} && {R}.sinistros.indicador) ? '#fef3f2' : '#ecfdf3'}}}};"
        f"border:1px solid {{{{({R} && {R}.sinistros.indicador) ? '#fda29b' : '#a6f4c5'}}}};"
        "border-radius:8px;padding:10px 14px;font-size:13px;"
        f"color:{{{{({R} && {R}.sinistros.indicador) ? '#b42318' : '#027a48'}}}}'>"
        f"{{{{({R} && {R}.sinistros.indicador) ? '⚠️ Constam registros de sinistro para este veículo.' : '✅ Nada consta: não há registro de sinistro indenizado para este veículo.'}}}}"
        "</div>",
        (1, 10, 39, 45),
        parent=f"{TABS_ID}-1",
    )
)
components.append(
    tabela(
        "tabelaSinistros",
        f"{{{{(({R} && {R}.sinistros.ocorrencias) || [])}}}}",
        [("Data", "data"), ("Tipo", "tipo"), ("Gravidade", "gravidade"), ("UF", "uf"), ("Descrição", "descricao")],
        (1, 65, 39, 400),
        parent=f"{TABS_ID}-1",
        mobile=(1, 65, 39, 350),
    )
)

components.append(
    texto_html(
        "indicadorLeiloes",
        f"<div style='background:{{{{({R} && {R}.leiloes.indicador) ? '#fffaeb' : '#ecfdf3'}}}};"
        f"border:1px solid {{{{({R} && {R}.leiloes.indicador) ? '#fec84b' : '#a6f4c5'}}}};"
        "border-radius:8px;padding:10px 14px;font-size:13px;"
        f"color:{{{{({R} && {R}.leiloes.indicador) ? '#93370d' : '#027a48'}}}}'>"
        f"{{{{({R} && {R}.leiloes.indicador) ? '⚠️ Este veículo possui passagem por leilão.' : '✅ Nada consta: não há registro de passagem por leilão.'}}}}"
        "</div>",
        (1, 10, 39, 45),
        parent=f"{TABS_ID}-2",
    )
)
components.append(
    tabela(
        "tabelaLeiloes",
        f"{{{{(({R} && {R}.leiloes.ocorrencias) || [])}}}}",
        [
            ("Data", "data"),
            ("Leiloeiro", "leiloeiro"),
            ("Comitente", "comitente"),
            ("Lote", "lote"),
            ("Condição", "condicao"),
            ("Nota de avaliação", "notaAvaliacao"),
        ],
        (1, 65, 39, 400),
        parent=f"{TABS_ID}-2",
        mobile=(1, 65, 39, 350),
    )
)

components.append(
    texto_html(
        "resumoFipe",
        "<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:10px'>"
        "<div style='background:#ffffff;border:1px solid #e6e8eb;border-radius:8px;padding:12px'>"
        "<div style='font-size:11px;text-transform:uppercase;color:#687076'>Código FIPE</div>"
        f"<div style='margin-top:4px;font-weight:700;color:#1b1f31'>{{{{({R} && {R}.fipe.codigoFipe) || '—'}}}}</div></div>"
        "<div style='background:#ffffff;border:1px solid #e6e8eb;border-radius:8px;padding:12px'>"
        "<div style='font-size:11px;text-transform:uppercase;color:#687076'>Valor de referência</div>"
        f"<div style='margin-top:4px;font-weight:700;font-size:17px;color:#3e63dd'>{{{{({R} && {R}.fipe.valor) || '—'}}}}</div></div>"
        "<div style='background:#ffffff;border:1px solid #e6e8eb;border-radius:8px;padding:12px'>"
        "<div style='font-size:11px;text-transform:uppercase;color:#687076'>Mês de referência</div>"
        f"<div style='margin-top:4px;font-weight:700;color:#1b1f31'>{{{{({R} && {R}.fipe.mesReferencia) || '—'}}}}</div></div>"
        "</div>",
        (1, 10, 39, 90),
        (1, 10, 39, 140),
        parent=f"{TABS_ID}-3",
    )
)
components.append(
    texto_html(
        "tituloHistoricoFipe",
        "<div style='font-size:14px;font-weight:700;color:#1b1f31'>Histórico de valores (12 meses)</div>",
        (1, 105, 39, 30),
        (1, 155, 39, 30),
        parent=f"{TABS_ID}-3",
    )
)
components.append(
    tabela(
        "tabelaHistoricoFipe",
        f"{{{{(({R} && {R}.fipe.historico) || [])}}}}",
        [("Mês de referência", "mes"), ("Valor", "valor")],
        (1, 140, 39, 330),
        parent=f"{TABS_ID}-3",
        mobile=(1, 190, 39, 300),
    )
)

components.append(
    texto_html(
        "rodapeInfo",
        "<div style='background:#ffffff;border:1px solid #e6e8eb;border-radius:10px;padding:14px 16px;"
        "font-size:12px;color:#687076;line-height:1.6'>"
        "<b style='color:#1b1f31'>Como conectar um provedor real</b><br/>"
        "1. Contrate um provedor de consulta veicular (Infosimples, API Brasil, Checkpro, Olho no Carro etc.).<br/>"
        "2. Em <b>Workspace settings → Workspace constants</b>, crie a constante <code>CONSULTA_VEICULAR_API_URL</code> "
        "com a URL do endpoint de consulta e o secret <code>CONSULTA_VEICULAR_API_KEY</code> com sua chave.<br/>"
        "3. Ajuste o mapeamento de campos na transformação da query <code>consultaProvedor</code> conforme a resposta do seu provedor.<br/><br/>"
        "⚖️ Os dados de situação legal têm origem nas bases oficiais (Senatran/Detran, SNG, RENAJUD) intermediadas pelo provedor contratado. "
        "O valor FIPE é obtido da API pública Parallelum quando o código FIPE está disponível. "
        "Este aplicativo tem caráter informativo e não substitui a certidão oficial do Detran."
        "</div>",
        (1, 835, 41, 130),
        (1, 965, 41, 190),
    )
)

COMP_BY_NAME = {c["name"]: c for c in components}

# ---------------------------------------------------------------------------
# Data sources e queries
# ---------------------------------------------------------------------------

data_sources = [
    {
        "id": DS_RESTAPI,
        "name": "restapidefault",
        "kind": "restapi",
        "type": "static",
        "pluginId": None,
        "appVersionId": VERSION_ID,
        "organizationId": None,
        "scope": "local",
        "createdAt": TS,
        "updatedAt": TS,
    },
    {
        "id": DS_RUNJS,
        "name": "runjsdefault",
        "kind": "runjs",
        "type": "static",
        "pluginId": None,
        "appVersionId": VERSION_ID,
        "organizationId": None,
        "scope": "local",
        "createdAt": TS,
        "updatedAt": TS,
    },
]

data_queries = [
    {
        "id": Q_ORQUESTRADOR,
        "name": "executarConsulta",
        "options": {
            "code": CODE_ORQUESTRADOR,
            "parameters": [],
            "runOnPageLoad": False,
            "showSuccessNotification": False,
            "notificationDuration": 5000,
        },
        "dataSourceId": DS_RUNJS,
        "appVersionId": VERSION_ID,
        "createdAt": TS,
        "updatedAt": TS,
    },
    {
        "id": Q_DEMO,
        "name": "consultaDemo",
        "options": {
            "code": CODE_DEMO,
            "parameters": [
                {"name": "identificador", "defaultValue": ""},
                {"name": "tipo", "defaultValue": "chassi"},
            ],
            "runOnPageLoad": False,
            "showSuccessNotification": False,
            "notificationDuration": 5000,
        },
        "dataSourceId": DS_RUNJS,
        "appVersionId": VERSION_ID,
        "createdAt": TS,
        "updatedAt": TS,
    },
    {
        "id": Q_PROVEDOR,
        "name": "consultaProvedor",
        "options": {
            "method": "post",
            "url": "{{constants.CONSULTA_VEICULAR_API_URL}}",
            "url_params": [["", ""]],
            "headers": [
                ["Content-Type", "application/json"],
                ["Authorization", "Bearer {{secrets.CONSULTA_VEICULAR_API_KEY}}"],
            ],
            "body": [["", ""]],
            "json_body": (
                "{{({ tipo: variables.tipoConsulta, identificador: variables.identificadorConsulta, "
                "chassi: variables.tipoConsulta === 'chassi' ? variables.identificadorConsulta : null, "
                "renavam: variables.tipoConsulta === 'renavam' ? variables.identificadorConsulta : null })}}"
            ),
            "body_toggle": True,
            "transformationLanguage": "javascript",
            "enableTransformation": True,
            "transformation": TRANSFORM_PROVEDOR,
            "runOnPageLoad": False,
            "showSuccessNotification": False,
            "notificationDuration": 5000,
        },
        "dataSourceId": DS_RESTAPI,
        "appVersionId": VERSION_ID,
        "createdAt": TS,
        "updatedAt": TS,
    },
    {
        "id": Q_FIPE,
        "name": "consultarFipe",
        "options": {
            "method": "get",
            "url": (
                "{{'https://parallelum.com.br/fipe/api/v2/cars/' + "
                "((variables.fipeParams && variables.fipeParams.codigo) || '') + '/years/' + "
                "((variables.fipeParams && variables.fipeParams.anoCodigo) || '')}}"
            ),
            "url_params": [["", ""]],
            "headers": [["", ""]],
            "body": [["", ""]],
            "json_body": None,
            "body_toggle": False,
            "transformationLanguage": "javascript",
            "enableTransformation": True,
            "transformation": TRANSFORM_FIPE,
            "runOnPageLoad": False,
            "showSuccessNotification": False,
            "notificationDuration": 5000,
        },
        "dataSourceId": DS_RESTAPI,
        "appVersionId": VERSION_ID,
        "createdAt": TS,
        "updatedAt": TS,
    },
]

# ---------------------------------------------------------------------------
# Eventos
# ---------------------------------------------------------------------------

events = [
    {
        "id": uid("event-botao-consultar"),
        "name": "onClick",
        "index": 0,
        "event": {
            "eventId": "onClick",
            "actionId": "run-query",
            "queryId": Q_ORQUESTRADOR,
            "queryName": "executarConsulta",
            "parameters": {},
        },
        "sourceId": COMP_BY_NAME["botaoConsultar"]["id"],
        "target": "component",
        "appVersionId": VERSION_ID,
        "createdAt": TS,
        "updatedAt": TS,
    },
    {
        "id": uid("event-input-enter"),
        "name": "onEnterPressed",
        "index": 0,
        "event": {
            "eventId": "onEnterPressed",
            "actionId": "run-query",
            "queryId": Q_ORQUESTRADOR,
            "queryName": "executarConsulta",
            "parameters": {},
        },
        "sourceId": COMP_BY_NAME["inputIdentificador"]["id"],
        "target": "component",
        "appVersionId": VERSION_ID,
        "createdAt": TS,
        "updatedAt": TS,
    },
]

# ---------------------------------------------------------------------------
# Montagem final (appV2)
# ---------------------------------------------------------------------------

app_version = {
    "id": VERSION_ID,
    "name": "v1",
    "definition": None,
    "globalSettings": {
        "hideHeader": True,
        "appInMaintenance": False,
        "canvasMaxWidth": 100,
        "canvasMaxWidthType": "%",
        "canvasMaxHeight": 2400,
        "canvasBackgroundColor": "#edeff5",
        "backgroundFxQuery": "",
        "appMode": "auto",
    },
    "pageSettings": {
        "properties": {
            "disableMenu": {"value": "{{true}}", "fxActive": False},
        }
    },
    "showViewerNavigation": False,
    "homePageId": PAGE_ID,
    "appId": APP_ID,
    "currentEnvironmentId": ENV_DEV,
    "promotedFrom": None,
    "createdAt": TS,
    "updatedAt": TS,
}

app_v2 = {
    "id": APP_ID,
    "type": "front-end",
    "name": "Consulta veicular Brasil",
    "slug": APP_ID,
    "isPublic": False,
    "isMaintenanceOn": False,
    "icon": "shield",
    "organizationId": ORG_ID,
    "currentVersionId": None,
    "userId": USER_ID,
    "workflowApiToken": None,
    "workflowEnabled": False,
    "createdAt": TS,
    "creationMode": "DEFAULT",
    "updatedAt": TS,
    "editingVersion": dict(app_version),
    "components": components,
    "pages": [
        {
            "id": PAGE_ID,
            "name": "Consulta",
            "handle": "consulta",
            "index": 1,
            "disabled": False,
            "hidden": False,
            "icon": None,
            "createdAt": TS,
            "updatedAt": TS,
            "autoComputeLayout": True,
            "appVersionId": VERSION_ID,
            "pageGroupIndex": None,
            "pageGroupId": None,
            "isPageGroup": False,
        }
    ],
    "events": events,
    "dataQueries": data_queries,
    "dataSources": data_sources,
    "appVersions": [app_version],
    "appEnvironments": [
        {
            "id": ENV_DEV,
            "organizationId": ORG_ID,
            "name": "development",
            "isDefault": False,
            "priority": 1,
            "enabled": True,
            "createdAt": TS,
            "updatedAt": TS,
        },
        {
            "id": ENV_STG,
            "organizationId": ORG_ID,
            "name": "staging",
            "isDefault": False,
            "priority": 2,
            "enabled": True,
            "createdAt": TS,
            "updatedAt": TS,
        },
        {
            "id": ENV_PROD,
            "organizationId": ORG_ID,
            "name": "production",
            "isDefault": True,
            "priority": 3,
            "enabled": True,
            "createdAt": TS,
            "updatedAt": TS,
        },
    ],
    "dataSourceOptions": [
        {
            "id": uid(f"dso-{ds['name']}-{env}"),
            "dataSourceId": ds["id"],
            "environmentId": env_id,
            "options": None,
            "createdAt": TS,
            "updatedAt": TS,
        }
        for ds in data_sources
        for env, env_id in (("dev", ENV_DEV), ("stg", ENV_STG), ("prod", ENV_PROD))
    ],
    "schemaDetails": {
        "multiPages": True,
        "multiEnv": True,
        "globalDataSources": True,
    },
}

definition = {
    "tooljet_database": [],
    "app": [{"definition": {"appV2": app_v2}}],
    "tooljet_version": "3.0.17-cloud-lts",
}

manifest = {
    "name": "Consulta veicular Brasil",
    "description": "Consulte a situação completa de um veículo brasileiro a partir do chassi ou do Renavam: dados cadastrais, situação legal (roubo/furto, gravame, RENAJUD, débitos), sinistros, leilões e valor de referência na tabela FIPE.",
    "widgets": ["Table", "Tabs"],
    "sources": [
        {"name": "RestAPI", "id": "restapi"},
        {"name": "Run JavaScript", "id": "runjs"},
    ],
    "id": "consulta-veicular-brasil",
    "category": "operations",
}

out_dir = os.path.dirname(os.path.abspath(__file__))
os.makedirs(out_dir, exist_ok=True)
with open(os.path.join(out_dir, "definition.json"), "w", encoding="utf-8") as f:
    json.dump(definition, f, ensure_ascii=False, indent=2)
    f.write("\n")
with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
    f.write("\n")

print("OK — arquivos gerados em", out_dir)
print("componentes:", len(components), "| queries:", len(data_queries), "| eventos:", len(events))

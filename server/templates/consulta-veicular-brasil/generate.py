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
Q_APIBRASIL = uid("q-consultaApiBrasil")
Q_DEMO = uid("q-consultaDemo")
Q_FIPE = uid("q-consultarFipe")
Q_DECODE_VIN = uid("q-decodificarVin")
Q_FIPE_MARCAS = uid("q-fipeMarcas")
Q_FIPE_MODELOS = uid("q-fipeModelos")
Q_FIPE_ANOS = uid("q-fipeAnos")
Q_FIPE_VALOR = uid("q-fipeValorSelecao")
Q_SEL_MARCA = uid("q-aoSelecionarMarcaFipe")
Q_SEL_MODELO = uid("q-aoSelecionarModeloFipe")
Q_SEL_ANO = uid("q-aoSelecionarAnoFipe")
Q_PLACA_GRATIS = uid("q-consultaPlacaGratuita")
Q_SEL_TIPO = uid("q-aoSelecionarTipoFipe")
Q_FIPE_HIST = uid("q-fipeHistorico")
Q_LAUDO = uid("q-gerarLaudoPdf")

# ---------------------------------------------------------------------------
# Códigos JavaScript das queries
# ---------------------------------------------------------------------------

CODE_ORQUESTRADOR = r"""// Orquestra a consulta veicular: valida a entrada, detecta o tipo de
// identificador (chassi/VIN, Renavam ou placa antiga/Mercosul), escolhe o
// modo (provedor real ou demonstração) e consolida o resultado no formato
// canônico usado por toda a interface.
const bruto = components.inputIdentificador.value || '';
const entrada = bruto.toUpperCase().replace(/[^A-Z0-9]/g, '');

await actions.setVariable('erroConsulta', '');
await actions.setVariable('resultado', null);
await actions.setVariable('fipeAuto', null);

const somenteDigitos = /^[0-9]+$/.test(entrada);
let tipo = null;
let subtipo = null;
if (entrada.length === 17 && /^[A-HJ-NPR-Z0-9]{17}$/.test(entrada)) {
  tipo = 'chassi';
} else if (somenteDigitos && entrada.length >= 9 && entrada.length <= 11) {
  tipo = 'renavam';
} else if (/^[A-Z]{3}[0-9]{4}$/.test(entrada)) {
  tipo = 'placa';
  subtipo = 'antiga';
} else if (/^[A-Z]{3}[0-9][A-Z][0-9]{2}$/.test(entrada)) {
  tipo = 'placa';
  subtipo = 'mercosul';
}

if (!tipo) {
  await actions.setVariable(
    'erroConsulta',
    'Identificador inválido. Informe um chassi/VIN com 17 caracteres (sem as letras I, O e Q), um Renavam com 9 a 11 dígitos ou uma placa no padrão antigo (ABC1234) ou Mercosul (ABC1D23).'
  );
  return null;
}

// Renavam tem dígito verificador oficial (módulo 11): valida offline para
// barrar erros de digitação antes de qualquer consulta.
if (tipo === 'renavam') {
  const d = entrada.padStart(11, '0');
  const corpo = d.slice(0, 10).split('').reverse();
  let soma = 0;
  for (let i = 0; i < 10; i++) soma += Number(corpo[i]) * (2 + (i % 8));
  let dv = (soma * 10) % 11;
  if (dv === 10) dv = 0;
  if (Number(d) === 0 || dv !== Number(d[10])) {
    await actions.setVariable(
      'erroConsulta',
      'Renavam inválido: o dígito verificador não confere. Confira a digitação no CRLV do veículo.'
    );
    return null;
  }
}

await actions.setVariable('tipoConsulta', tipo);
await actions.setVariable('subtipoPlaca', subtipo);
await actions.setVariable('identificadorConsulta', entrada);

// Objetos lidos de queries (getData) vêm do store do app e são imutáveis;
// clona antes de qualquer mutação (ex.: anexar o resultado FIPE).
const clonar = (obj) => (obj ? JSON.parse(JSON.stringify(obj)) : obj);

const urlProvedor =
  typeof constants !== 'undefined' && constants && constants.CONSULTA_VEICULAR_API_URL
    ? String(constants.CONSULTA_VEICULAR_API_URL)
    : '';
const apiConfigurada = urlProvedor.indexOf('http') === 0;
// Fase 1: quando a URL aponta para a APIBrasil, usa o adaptador dedicado
// (headers Bearer + DeviceToken; consulta somente por placa).
const modoApiBrasil = apiConfigurada && urlProvedor.toLowerCase().indexOf('apibrasil') !== -1;
// Modo gratuito: sem provedor pago configurado, um chassi é decodificado com
// dados reais (tabela WMI local + NHTSA vPIC) e uma placa pode ser consultada
// em um serviço com cota gratuita (constante PLACA_API_URL com o marcador
// {placa}). Renavam — e placa sem PLACA_API_URL — caem no modo demo.
const placaGratuitaConfigurada =
  typeof constants !== 'undefined' &&
  constants &&
  constants.PLACA_API_URL &&
  String(constants.PLACA_API_URL).indexOf('http') === 0;
const modoGratuito =
  !apiConfigurada && (tipo === 'chassi' || (tipo === 'placa' && placaGratuitaConfigurada));
await actions.setVariable('modoDemo', !apiConfigurada && !modoGratuito);
await actions.setVariable('modoGratuito', modoGratuito);

if (modoGratuito && tipo === 'placa') {
  // Consulta gratuita por placa no serviço configurado pelo usuário.
  let resultadoPlaca = null;
  try {
    await queries.consultaPlacaGratuita.run();
    resultadoPlaca = clonar(queries.consultaPlacaGratuita.getData());
  } catch (erro) {
    await actions.setVariable(
      'erroConsulta',
      'A consulta gratuita de placa falhou: ' + ((erro && erro.message) || erro) +
        '. Verifique a cota e a chave configuradas em PLACA_API_URL.'
    );
    return null;
  }
  if (!resultadoPlaca || !resultadoPlaca.veiculo) {
    await actions.setVariable(
      'erroConsulta',
      'O serviço gratuito de placa não retornou dados para esta placa. Verifique a cota diária e a chave em PLACA_API_URL.'
    );
    return null;
  }

  // Valoração FIPE: usa o código FIPE quando o serviço retorna; caso contrário,
  // tenta casar marca/modelo/ano com a tabela oficial (mesma cadeia do chassi).
  const tipoTextoPlaca = String(resultadoPlaca.veiculo.tipo || '').toUpperCase();
  const tipoFipePlaca =
    tipoTextoPlaca.indexOf('MOTO') !== -1
      ? 'motos'
      : tipoTextoPlaca.indexOf('CAMINH') !== -1 || tipoTextoPlaca.indexOf('TRATOR') !== -1
      ? 'caminhoes'
      : 'carros';
  if (!(resultadoPlaca.fipe && resultadoPlaca.fipe.valor)) {
CADEIA_FIPE(resultadoPlaca, resultadoPlaca.veiculo.marca, resultadoPlaca.veiculo.modelo, resultadoPlaca.veiculo.anoModelo, tipoFipePlaca)
  }

  await actions.setVariable('resultado', resultadoPlaca);
  return resultadoPlaca;
}

if (modoGratuito) {
  // Tabela WMI (3 primeiros caracteres) dos fabricantes mais comuns no Brasil.
  const TABELA_WMI = {
    '9BW': ['Volkswagen', 'Brasil'], '9BD': ['Fiat', 'Brasil'], '9BG': ['Chevrolet', 'Brasil'],
    '9BF': ['Ford', 'Brasil'], '9BR': ['Toyota', 'Brasil'], '93H': ['Honda', 'Brasil'],
    '93Y': ['Renault', 'Brasil'], '9BM': ['Mercedes-Benz', 'Brasil'], '95P': ['CAOA/Hyundai', 'Brasil'],
    '9BH': ['Hyundai', 'Brasil'], '93X': ['Mitsubishi', 'Brasil'], '94D': ['Nissan', 'Brasil'],
    '8AW': ['Volkswagen', 'Argentina'], '8AP': ['Fiat', 'Argentina'], '8AG': ['Chevrolet', 'Argentina'],
    '8AF': ['Ford', 'Argentina'], '8A1': ['Renault', 'Argentina'], '8AJ': ['Toyota', 'Argentina'],
    '9C2': ['Honda Motos', 'Brasil'], '9C6': ['Yamaha', 'Brasil'], '9CD': ['Suzuki Motos', 'Brasil'],
    '9BS': ['Scania', 'Brasil'], '953': ['VW Caminhões', 'Brasil'], '9BV': ['Volvo', 'Brasil'],
    '988': ['Jeep/Stellantis', 'Brasil'], '98R': ['Chery/CAOA', 'Brasil'], '95Y': ['BYD', 'Brasil'],
  };
  const PAIS_POR_INICIAL = {
    '9': 'Brasil', '8': 'América do Sul', '3': 'México/América do Norte', '1': 'EUA', '4': 'EUA',
    '5': 'EUA', '2': 'Canadá', 'W': 'Alemanha', 'J': 'Japão', 'K': 'Coreia do Sul', 'L': 'China',
    'S': 'Reino Unido', 'V': 'França/Espanha', 'Z': 'Itália', 'Y': 'Suécia/Finlândia', 'T': 'Europa Central',
  };
  const MAPA_ANO = {
    A: 1980, B: 1981, C: 1982, D: 1983, E: 1984, F: 1985, G: 1986, H: 1987, J: 1988, K: 1989,
    L: 1990, M: 1991, N: 1992, P: 1993, R: 1994, S: 1995, T: 1996, V: 1997, W: 1998, X: 1999,
    Y: 2000, 1: 2001, 2: 2002, 3: 2003, 4: 2004, 5: 2005, 6: 2006, 7: 2007, 8: 2008, 9: 2009,
  };
  const wmi = entrada.slice(0, 3);
  const local = TABELA_WMI[wmi] || null;
  const pais = local ? local[1] : PAIS_POR_INICIAL[entrada[0]] || 'Não identificado';
  let anoLocal = MAPA_ANO[entrada[9]] !== undefined ? MAPA_ANO[entrada[9]] : null;
  if (anoLocal) {
    const anoAtual = new Date().getFullYear();
    while (anoLocal + 30 <= anoAtual + 1) anoLocal += 30;
  }

  let vpic = null;
  try {
    await queries.decodificarVin.run();
    vpic = queries.decodificarVin.getData();
  } catch (erro) {
    // vPIC é complementar; a decodificação local cobre fabricante, país e ano.
  }
  vpic = vpic || {};

  const naoVerificado = 'Não coberto na consulta gratuita';
  const resultadoGratuito = {
    veiculo: {
      chassi: entrada,
      renavam: '—',
      placa: '—',
      marca: vpic.marca || (local ? local[0] : '—'),
      modelo: vpic.modelo || (vpic.fabricante && vpic.fabricante !== vpic.marca ? vpic.fabricante : '—'),
      anoFabricacao: '—',
      anoModelo: vpic.anoModelo || anoLocal || '—',
      cor: '—',
      combustivel: vpic.combustivel || '—',
      codigoCombustivel: null,
      municipio: '—',
      uf: '—',
      codigoFipe: '',
      procedencia: pais,
      tipo: vpic.tipoVeiculo || '—',
      situacao: 'Estrutura do chassi válida (decodificação WMI/vPIC)',
    },
    situacaoLegal: {
      status: 'Verificação parcial',
      rouboFurto: { indicador: null, detalhes: naoVerificado + ' — requer provedor com acesso às bases oficiais.' },
      gravame: { status: naoVerificado, financeira: null, dataInclusao: null },
      debitos: { ipva: naoVerificado, licenciamento: naoVerificado, multas: naoVerificado },
      renajud: naoVerificado,
      restricoes: [],
    },
    sinistros: { indicador: null, ocorrencias: [] },
    leiloes: { indicador: null, ocorrencias: [] },
    fipe: { codigoFipe: '', valor: '', mesReferencia: '', historico: [] },
    metadados: {
      fonte: 'Decodificação gratuita do chassi (tabela WMI + NHTSA vPIC)',
      modoDemo: false,
      consultadoEm: new Date().toLocaleString('pt-BR'),
    },
  };
  // Avaliação FIPE automática: casa a marca/modelo/ano decodificados do chassi
  // com a tabela FIPE oficial, no segmento correto (carros/motos/caminhões).
  const tipoVpic = String(vpic.tipoVeiculo || '').toUpperCase();
  const tipoFipeChassi =
    ['9C2', '9C6', '9CD'].indexOf(wmi) !== -1 || tipoVpic.indexOf('MOTORCYCLE') !== -1
      ? 'motos'
      : ['9BS', '953', '9BV'].indexOf(wmi) !== -1 || tipoVpic.indexOf('TRUCK') !== -1
      ? 'caminhoes'
      : 'carros';
CADEIA_FIPE(resultadoGratuito, resultadoGratuito.veiculo.marca, vpic.modelo, resultadoGratuito.veiculo.anoModelo, tipoFipeChassi)

  await actions.setVariable('resultado', resultadoGratuito);
  return resultadoGratuito;
}

if (modoApiBrasil && tipo !== 'placa') {
  await actions.setVariable(
    'erroConsulta',
    'Na integração atual (APIBrasil — Fase 1), a consulta com dados reais é feita pela placa do veículo. Informe a placa, ou configure um provedor completo para consultar por chassi ou Renavam.'
  );
  return null;
}

let resultado = null;
try {
  if (modoApiBrasil) {
    await queries.consultaApiBrasil.run();
    resultado = clonar(queries.consultaApiBrasil.getData());
  } else if (apiConfigurada) {
    await queries.consultaProvedor.run();
    resultado = clonar(queries.consultaProvedor.getData());
  } else {
    await queries.consultaDemo.run({ identificador: entrada, tipo: tipo, subtipo: subtipo });
    resultado = clonar(queries.consultaDemo.getData());
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
// pública Parallelum) quando o provedor devolve o código FIPE mas não o valor.
const semValorFipe = !(resultado.fipe && resultado.fipe.valor);
if (apiConfigurada && semValorFipe && resultado.veiculo.codigoFipe && resultado.veiculo.anoModelo) {
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



def _cadeia_fipe_js(alvo, marca, modelo, ano, tipo):
    """Emite o bloco JS da cadeia FIPE automática (marca → modelo → ano → valor).

    Reuso em tempo de geração: a cadeia precisa rodar inline no orquestrador
    porque resultados de queries disparadas por uma query runjs aninhada não
    ficam visíveis no snapshot de estado de quem a chamou.
    """
    return f"""  try {{
    const norm = (s) => String(s || '').toLowerCase().replace(/[^a-z0-9]/g, '');
    let marcas = queries.fipeMarcas.getData();
    if (!marcas || !marcas.length) {{
      await queries.fipeMarcas.run();
      marcas = queries.fipeMarcas.getData() || [];
    }}
    const alvoMarca = norm({marca});
    const marcaFipe =
      alvoMarca.length > 2
        ? marcas.find((m) => norm(m.nome).indexOf(alvoMarca) !== -1 || alvoMarca.indexOf(norm(m.nome)) !== -1)
        : null;
    if (marcaFipe) {{
      await actions.setVariable('fipeAuto', {{ tipo: {tipo}, marca: String(marcaFipe.codigo) }});
      await queries.fipeModelos.run();
      const modelos = queries.fipeModelos.getData() || [];
      const alvoModelo = norm({modelo});
      let modeloFipe = alvoModelo.length > 1 ? modelos.find((m) => norm(m.nome).indexOf(alvoModelo) !== -1) : null;
      if (!modeloFipe && alvoModelo.length > 1) {{
        const primeira = norm(String({modelo} || '').split(/[\\s/]+/)[0]);
        if (primeira.length > 2) modeloFipe = modelos.find((m) => norm(m.nome).indexOf(primeira) !== -1);
      }}
      if (modeloFipe) {{
        await actions.setVariable('fipeAuto', {{ tipo: {tipo}, marca: String(marcaFipe.codigo), modelo: String(modeloFipe.codigo) }});
        await queries.fipeAnos.run();
        const anos = queries.fipeAnos.getData() || [];
        const alvoAno = String({ano} || '').replace(/[^0-9]/g, '').slice(0, 4);
        const anoFipe = alvoAno
          ? anos.find((a) => String(a.codigo).indexOf(alvoAno) === 0 || String(a.nome).indexOf(alvoAno) !== -1)
          : null;
        if (anoFipe) {{
          await actions.setVariable('fipeAuto', {{
            tipo: {tipo},
            marca: String(marcaFipe.codigo),
            modelo: String(modeloFipe.codigo),
            ano: String(anoFipe.codigo),
          }});
          await queries.fipeValorSelecao.run();
          const fipeOficial = queries.fipeValorSelecao.getData();
          if (fipeOficial && fipeOficial.valor) {{
            {alvo}.fipe = {{
              codigoFipe: fipeOficial.codigoFipe,
              valor: fipeOficial.valor,
              mesReferencia: fipeOficial.mesReferencia,
              historico: [],
            }};
            {alvo}.veiculo.codigoFipe = fipeOficial.codigoFipe;
            // Evolução de valores: com a constante FIPE_API_TOKEN (chave gratuita
            // da Parallelum v2), busca o histórico real para o gráfico.
            const temTokenFipe =
              typeof constants !== 'undefined' && constants && constants.FIPE_API_TOKEN;
            if (temTokenFipe && fipeOficial.codigoFipe) {{
              await actions.setVariable('fipeAuto', {{
                tipo: {tipo},
                marca: String(marcaFipe.codigo),
                modelo: String(modeloFipe.codigo),
                ano: String(anoFipe.codigo),
                codigoFipe: String(fipeOficial.codigoFipe),
              }});
              try {{
                await queries.fipeHistorico.run();
                const historicoReal = queries.fipeHistorico.getData();
                if (historicoReal && historicoReal.length) {{
                  {alvo}.fipe.historico = historicoReal;
                }}
              }} catch (erroHist) {{
                // Histórico é complementar ao valor vigente.
              }}
            }}
          }}
        }}
      }}
    }}
  }} catch (erro) {{
    // A valoração FIPE é complementar; o usuário pode usar a aba Tabela FIPE.
  }}"""


import re as _re

CODE_ORQUESTRADOR = _re.sub(
    r"^CADEIA_FIPE\(([^,]+), ([^,]+), ([^,]+), ([^,]+), ([^)]+)\)$",
    lambda m: _cadeia_fipe_js(
        m.group(1).strip(), m.group(2).strip(), m.group(3).strip(), m.group(4).strip(), m.group(5).strip()
    ),
    CODE_ORQUESTRADOR,
    flags=_re.M,
)

CODE_DEMO = r"""// Modo demonstração: gera um laudo veicular simulado e determinístico a
// partir do identificador informado, seguindo o mesmo contrato de dados do
// provedor real. Permite explorar o app sem contratar uma API paga.
const id = (parameters && parameters.identificador) || variables.identificadorConsulta || '9BWZZZ377VT004251';
const tipo = (parameters && parameters.tipo) || variables.tipoConsulta || 'chassi';
const subtipo = (parameters && parameters.subtipo) || variables.subtipoPlaca || null;

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
const placaGerada =
  pick(['ABC', 'BRA', 'RIO', 'SPX', 'MGV'], 19) + digitos.slice(2, 3) + pick(['A', 'B', 'C', 'D', 'E'], 23) + digitos.slice(5, 7);
// Placa informada pelo usuário prevalece; padrão antigo é exibido com hífen.
const placa =
  tipo === 'placa' ? (subtipo === 'antiga' ? id.slice(0, 3) + '-' + id.slice(3) : id) : placaGerada;

return {
  veiculo: {
    chassi: chassi,
    renavam: renavam,
    placa: placa,
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
    placa: texto(v.placa, variables.tipoConsulta === 'placa' ? variables.identificadorConsulta : '—'),
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

TRANSFORM_APIBRASIL = r"""// Normaliza a resposta da APIBrasil (API Placa Dados — Fase 1) para o
// contrato canônico do app. A resposta usual tem o formato
// { error, message, response: { chassi, marca, modelo, ano, anoModelo, cor,
//   municipio, uf, situacao, extra: {...}, fipe: { dados: [{ codigo_fipe,
//   texto_valor, mes_referencia, texto_marca, texto_modelo }] } } }.
if (data && data.error === true) {
  throw new Error(data.message || 'A APIBrasil retornou erro para esta consulta.');
}
const candidatoRaiz = data && (data.response || data.dados);
const raiz = (candidatoRaiz && typeof candidatoRaiz === 'object' ? candidatoRaiz : data) || {};
const v = raiz.veiculo || raiz;
const extra = v.extra || raiz.extra || {};
const fipeBruto = raiz.fipe && (raiz.fipe.dados || raiz.fipe);
const fipeItem = (Array.isArray(fipeBruto) ? fipeBruto[0] : fipeBruto) || {};

const texto = (valor, padrao) => {
  if (valor === undefined || valor === null || valor === '') return padrao;
  return String(valor);
};

// Situação SINESP/base estadual: "Sem restrição", "Roubo/Furto" etc.
const situacao = texto(v.situacao || extra.situacao_veiculo, '');
const situacaoMin = situacao.toLowerCase();
let indicadorRouboFurto = null;
if (situacaoMin.indexOf('roubo') !== -1 || situacaoMin.indexOf('furto') !== -1) indicadorRouboFurto = true;
else if (situacaoMin.indexOf('sem restri') !== -1 || situacaoMin.indexOf('circula') !== -1) indicadorRouboFurto = false;

// Restrições genéricas dos agregados (restricao_1..restricao_4 e afins).
const restricoes = [];
[v, extra].forEach((origem) => {
  Object.keys(origem || {}).forEach((chave) => {
    if (/^restricao/i.test(chave)) {
      const valor = texto(origem[chave], '');
      if (valor && !/^sem restri/i.test(valor) && valor !== '0') {
        restricoes.push({ tipo: valor, descricao: 'Apontamento retornado pela base consultada.', orgao: '—' });
      }
    }
  });
});

return {
  veiculo: {
    chassi: texto(v.chassi || extra.chassi, '—'),
    renavam: texto(v.renavam || extra.renavam, '—'),
    placa: texto(v.placa, variables.identificadorConsulta),
    marca: texto(v.marca || v.MARCA || fipeItem.texto_marca, '—'),
    modelo: texto(v.modelo || v.MODELO || fipeItem.texto_modelo, '—'),
    anoFabricacao: texto(v.ano || v.anoFabricacao || extra.ano_fabricacao, '—'),
    anoModelo: texto(v.anoModelo || v.ano_modelo || extra.ano_modelo || fipeItem.ano_modelo, ''),
    cor: texto(v.cor || extra.cor_veiculo, '—'),
    combustivel: texto(v.combustivel || extra.combustivel || fipeItem.combustivel, '—'),
    codigoCombustivel: null,
    municipio: texto(v.municipio || extra.municipio, '—'),
    uf: texto(v.uf || extra.uf || extra.uf_placa, '—'),
    codigoFipe: texto(fipeItem.codigo_fipe || fipeItem.codigoFipe || v.codigo_fipe, ''),
    procedencia: texto(v.procedencia || extra.procedencia, '—'),
    tipo: texto(v.tipo_veiculo || extra.tipo_veiculo || v.segmento, '—'),
    situacao: texto(situacao, '—'),
  },
  situacaoLegal: {
    status: indicadorRouboFurto || restricoes.length > 0 ? 'Com restrições' : indicadorRouboFurto === false ? 'Regular' : 'Verificação parcial',
    rouboFurto: {
      indicador: indicadorRouboFurto,
      detalhes:
        indicadorRouboFurto === true
          ? 'Constam registros de roubo ou furto na base consultada.'
          : indicadorRouboFurto === false
          ? 'Nada consta na base consultada.'
          : 'Indicador não retornado pelo plano atual do provedor.',
    },
    gravame: {
      status: texto(extra.gravame || v.gravame, 'Não informado'),
      financeira: null,
      dataInclusao: null,
    },
    debitos: {
      ipva: 'Não informado',
      licenciamento: 'Não informado',
      multas: 'Não informado',
    },
    renajud: 'Não informado',
    restricoes: restricoes,
  },
  // Fase 1 (APIBrasil): indicadores de sinistro e leilão não são cobertos —
  // ficam como null para a interface exibir o estado "não coberto".
  sinistros: { indicador: null, ocorrencias: [] },
  leiloes: { indicador: null, ocorrencias: [] },
  fipe: {
    codigoFipe: texto(fipeItem.codigo_fipe || fipeItem.codigoFipe, ''),
    valor: texto(fipeItem.texto_valor || fipeItem.valor, ''),
    mesReferencia: texto(fipeItem.mes_referencia || fipeItem.mesReferencia, ''),
    historico: [],
  },
  metadados: {
    fonte: 'APIBrasil — API Placa Dados (Fase 1)',
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


def tabela(name, data_expr, columns, desktop, parent=None, mobile=None, visibility="{{true}}"):
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
            # True é obrigatório nas versões atuais do ToolJet: com o flag desligado,
            # generateColumns retorna undefined quando os dados chegam e o widget quebra.
            # Colunas explícitas (não-autogeradas) sempre persistem no merge.
            "autogenerateColumns": {"value": True},
            "visible": {"value": visibility},
            "visibility": {"value": visibility},
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
        "Situação legal, sinistros, leilões e valor de referência FIPE a partir do chassi/VIN, do Renavam ou da placa (antiga ou Mercosul)."
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
            "placeholder": {"value": "Chassi (17 caract.), Renavam (9–11 dígitos) ou placa (ABC1234 / ABC1D23)"},
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
        "botaoLaudo",
        "Button",
        (34, 30, 8, 40),
        (22, 10, 19, 40),
        properties={
            "text": {"value": "🖨 Gerar laudo (PDF)"},
            "loadingState": {"value": "{{queries.gerarLaudoPdf.isLoading}}", "fxActive": True},
            "visibility": {"value": "{{!!variables.resultado}}"},
            "disabledState": {"value": "{{false}}"},
            "tooltip": {"value": "Abre o laudo em uma nova janela; use Salvar como PDF no diálogo de impressão."},
        },
        styles={
            "backgroundColor": {"value": "#ffffff"},
            "textColor": {"value": "#3e63dd"},
            "borderRadius": {"value": "{{8}}"},
            "borderColor": {"value": "#3e63dd"},
            "loaderColor": {"value": "#3e63dd"},
            "padding": {"value": "default"},
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
    "if (/^[0-9]{9,11}$/.test(e)) { const d = e.padStart(11, '0'); const c = d.slice(0, 10).split('').reverse(); "
    "let s = 0; for (let i = 0; i < 10; i++) s += Number(c[i]) * (2 + (i % 8)); let dv = (s * 10) % 11; if (dv === 10) dv = 0; "
    "return dv === Number(d[10]) ? '✔ Renavam válido (DV confere)' : '⚠ Renavam com dígito verificador inválido'; } "
    "if (/^[A-Z]{3}[0-9]{4}$/.test(e)) return '✔ Placa antiga detectada'; "
    "if (/^[A-Z]{3}[0-9][A-Z][0-9]{2}$/.test(e)) return '✔ Placa Mercosul detectada'; "
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
        "bannerGratuito",
        "<div style='background:#eef4ff;border:1px solid #b2ccff;border-radius:8px;padding:10px 14px;"
        "color:#1d4ed8;font-size:13px'>🆓 <b>Modo gratuito:</b> dados reais de fontes gratuitas — "
        "decodificação do chassi (padrão VIN + base NHTSA vPIC), consulta de placa no serviço configurado "
        "e tabela FIPE oficial. Situação legal completa, sinistros e leilões requerem um provedor pago.</div>",
        (1, 158, 41, 40),
        (1, 205, 41, 60),
        visibility="{{!variables.erroConsulta && variables.modoGratuito === true && !!variables.resultado}}",
    )
)

components.append(
    texto_html(
        "estadoVazio",
        "<div style='background:#ffffff;border:1px dashed #c1c8cd;border-radius:12px;padding:28px;"
        "text-align:center;color:#687076'>"
        "<div style='font-size:34px'>🔎</div>"
        "<div style='margin-top:8px;font-size:16px;font-weight:600;color:#1b1f31'>Informe um chassi/VIN, Renavam ou placa para começar</div>"
        "<div style='margin-top:6px;font-size:13px'>Chassi: <code>9BWZZZ377VT004251</code> &nbsp;•&nbsp; "
        "Renavam: <code>12345678900</code> &nbsp;•&nbsp; "
        "Placa antiga: <code>ABC-1234</code> &nbsp;•&nbsp; Placa Mercosul: <code>ABC1D23</code></div>"
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
    f"({R} && {R}.situacaoLegal.status === 'Com restrições') ? '#f79009' : "
    f"({R} && {R}.situacaoLegal.status === 'Verificação parcial') ? '#475467' : '#f04438'}}}}"
)
components.append(
    card(
        "cardSituacao",
        "Situação legal",
        f"{{{{({R} && {R}.situacaoLegal.status) || '—'}}}}",
        (25, 210, 9, 100),
        cor_valor=STATUS_COR,
        subtitulo_expr=(
            f"{{{{({R} ? {R}.sinistros.indicador : null) === true ? 'Com sinistro' : ({R} ? {R}.sinistros.indicador : null) === false ? 'Sem sinistro' : 'Sinistro n/d'}}}} • "
            f"{{{{({R} ? {R}.leiloes.indicador : null) === true ? 'Com leilão' : ({R} ? {R}.leiloes.indicador : null) === false ? 'Sem leilão' : 'Leilão n/d'}}}}"
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
    (1, 320, 41, 560),
    (1, 430, 41, 740),
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
    f"<div style='margin-top:4px;font-weight:700;color:{{{{({R} ? {R}.situacaoLegal.rouboFurto.indicador : null) === true ? '#f04438' : ({R} ? {R}.situacaoLegal.rouboFurto.indicador : null) === false ? '#12b76a' : '#475467'}}}}'>"
    f"{{{{({R} ? {R}.situacaoLegal.rouboFurto.indicador : null) === true ? 'Consta ocorrência' : ({R} ? {R}.situacaoLegal.rouboFurto.indicador : null) === false ? 'Nada consta' : 'Não verificado'}}}}</div>"
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

SIN = f"({R} ? {R}.sinistros.indicador : null)"
components.append(
    texto_html(
        "indicadorSinistros",
        f"<div style='background:{{{{{SIN} === true ? '#fef3f2' : {SIN} === false ? '#ecfdf3' : '#f2f4f7'}}}};"
        f"border:1px solid {{{{{SIN} === true ? '#fda29b' : {SIN} === false ? '#a6f4c5' : '#d0d5dd'}}}};"
        "border-radius:8px;padding:10px 14px;font-size:13px;"
        f"color:{{{{{SIN} === true ? '#b42318' : {SIN} === false ? '#027a48' : '#475467'}}}}'>"
        f"{{{{{SIN} === true ? '⚠️ Constam registros de sinistro para este veículo.' : {SIN} === false ? '✅ Nada consta: não há registro de sinistro indenizado para este veículo.' : 'ℹ️ Indicador de sinistro não coberto pelo provedor atual (disponível na Fase 2, com provedor completo).'}}}}"
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

LEI = f"({R} ? {R}.leiloes.indicador : null)"
components.append(
    texto_html(
        "indicadorLeiloes",
        f"<div style='background:{{{{{LEI} === true ? '#fffaeb' : {LEI} === false ? '#ecfdf3' : '#f2f4f7'}}}};"
        f"border:1px solid {{{{{LEI} === true ? '#fec84b' : {LEI} === false ? '#a6f4c5' : '#d0d5dd'}}}};"
        "border-radius:8px;padding:10px 14px;font-size:13px;"
        f"color:{{{{{LEI} === true ? '#93370d' : {LEI} === false ? '#027a48' : '#475467'}}}}'>"
        f"{{{{{LEI} === true ? '⚠️ Este veículo possui passagem por leilão.' : {LEI} === false ? '✅ Nada consta: não há registro de passagem por leilão.' : 'ℹ️ Indicador de leilão não coberto pelo provedor atual (disponível na Fase 2, com provedor completo).'}}}}"
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

def dropdown_fipe(name, placeholder, values_expr, display_expr, loading_expr, value_expr, desktop, mobile):
    return component(
        name,
        "DropDown",
        desktop,
        mobile,
        parent=f"{TABS_ID}-3",
        properties={
            "label": {"value": ""},
            "placeholder": {"value": placeholder},
            "value": {"value": value_expr},
            "values": {"value": values_expr},
            "display_values": {"value": display_expr},
            "loadingState": {"value": loading_expr},
            "visibility": {"value": "{{true}}"},
            "disabledState": {"value": "{{false}}"},
        },
        styles={"borderRadius": {"value": "8"}},
    )


components.append(
    texto_html(
        "tituloFipeLive",
        "<div style='font-size:14px;font-weight:700;color:#1b1f31'>Avaliação FIPE oficial "
        "<span style='color:#687076;font-weight:400'>(gratuita — selecione tipo, marca, modelo e ano)</span></div>",
        (1, 10, 39, 30),
        (1, 10, 39, 30),
        parent=f"{TABS_ID}-3",
    )
)
components.append(
    dropdown_fipe(
        "selectTipoFipe",
        "Tipo",
        '{{["carros","motos","caminhoes"]}}',
        '{{["Carros","Motos","Caminhões"]}}',
        "{{false}}",
        "{{(variables.fipeAuto && variables.fipeAuto.tipo) || 'carros'}}",
        (1, 45, 8, 40),
        (1, 45, 39, 40),
    )
)
components.append(
    dropdown_fipe(
        "selectMarcaFipe",
        "Marca",
        "{{(queries.fipeMarcas.data || []).map(m => m.codigo)}}",
        "{{(queries.fipeMarcas.data || []).map(m => m.nome)}}",
        "{{queries.fipeMarcas.isLoading}}",
        "{{(variables.fipeAuto && variables.fipeAuto.marca) || ''}}",
        (10, 45, 10, 40),
        (1, 90, 39, 40),
    )
)
components.append(
    dropdown_fipe(
        "selectModeloFipe",
        "Modelo",
        "{{(queries.fipeModelos.data || []).map(m => m.codigo)}}",
        "{{(queries.fipeModelos.data || []).map(m => m.nome)}}",
        "{{queries.fipeModelos.isLoading}}",
        "{{(variables.fipeAuto && variables.fipeAuto.modelo) || ''}}",
        (21, 45, 11, 40),
        (1, 135, 39, 40),
    )
)
components.append(
    dropdown_fipe(
        "selectAnoFipe",
        "Ano",
        "{{(queries.fipeAnos.data || []).map(a => a.codigo)}}",
        "{{(queries.fipeAnos.data || []).map(a => a.nome)}}",
        "{{queries.fipeAnos.isLoading}}",
        "{{(variables.fipeAuto && variables.fipeAuto.ano) || ''}}",
        (33, 45, 7, 40),
        (1, 180, 39, 40),
    )
)
components.append(
    texto_html(
        "resultadoFipeLive",
        "<div style='background:#eef4ff;border:1px solid #b2ccff;border-radius:10px;padding:14px 16px'>"
        "{{(queries.fipeValorSelecao.data && queries.fipeValorSelecao.data.valor) ? "
        "('<span style=\"font-size:22px;font-weight:800;color:#1d4ed8\">' + queries.fipeValorSelecao.data.valor + '</span>"
        " <span style=\"color:#475467;font-size:13px\">— ' + queries.fipeValorSelecao.data.marca + ' ' + "
        "queries.fipeValorSelecao.data.modelo + ' ' + queries.fipeValorSelecao.data.anoModelo + "
        "' • Código FIPE ' + queries.fipeValorSelecao.data.codigoFipe + ' • Ref. ' + "
        "queries.fipeValorSelecao.data.mesReferencia + '</span>') : "
        "'<span style=\"color:#687076;font-size:13px\">Selecione marca, modelo e ano acima para consultar o valor oficial da tabela FIPE.</span>'}}"
        "</div>",
        (1, 95, 39, 70),
        (1, 225, 39, 90),
        parent=f"{TABS_ID}-3",
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
        (1, 175, 39, 90),
        (1, 325, 39, 140),
        parent=f"{TABS_ID}-3",
    )
)
components.append(
    texto_html(
        "tituloHistoricoFipe",
        "<div style='font-size:14px;font-weight:700;color:#1b1f31'>Evolução do valor FIPE</div>",
        (1, 270, 39, 30),
        (1, 470, 39, 30),
        parent=f"{TABS_ID}-3",
        visibility="{{(((queries.fipeHistorico.data && queries.fipeHistorico.data.length) ? queries.fipeHistorico.data : ((variables.resultado && variables.resultado.fipe.historico) || []))).length > 1}}",
    )
)
components.append(
    component(
        "graficoHistoricoFipe",
        "Chart",
        (1, 305, 39, 250),
        (1, 505, 39, 250),
        parent=f"{TABS_ID}-3",
        properties={
            "title": {"value": ""},
            "plotFromJson": {"value": "{{true}}"},
            "jsonDescription": {"value": "{{(() => { const h = (((queries.fipeHistorico.data && queries.fipeHistorico.data.length) ? queries.fipeHistorico.data : ((variables.resultado && variables.resultado.fipe.historico) || []))); const y = h.map((i) => Number(String(i.valor).replace(/[^0-9,]/g, '').replace(',', '.'))); return JSON.stringify({ data: [ { x: h.map((i) => i.mes), y: y, type: 'scatter', mode: 'lines+markers', line: { color: '#3e63dd', width: 3, shape: 'spline' }, marker: { size: 6, color: '#3e63dd' }, hovertemplate: '%{x}: %{y:,.0f}<extra></extra>' } ], layout: { margin: { t: 12, r: 16, b: 64, l: 72 }, yaxis: { tickprefix: 'R$ ' } } } ); } )()}}"},
            "loadingState": {"value": "{{queries.fipeHistorico.isLoading}}"},
            "visibility": {"value": "{{(((queries.fipeHistorico.data && queries.fipeHistorico.data.length) ? queries.fipeHistorico.data : ((variables.resultado && variables.resultado.fipe.historico) || []))).length > 1}}"},
        },
        styles={"padding": {"value": "6"}, "borderRadius": {"value": "8"}},
    )
)

components.append(
    texto_html(
        "rodapeInfo",
        "<div style='background:#ffffff;border:1px solid #e6e8eb;border-radius:10px;padding:14px 16px;"
        "font-size:12px;color:#687076;line-height:1.6'>"
        "<b style='color:#1b1f31'>Fontes de dados</b><br/>"
        "<b>Modo gratuito (padrão):</b> chassi decodificado com dados reais (padrão VIN/WMI + base pública NHTSA vPIC) "
        "e valores oficiais da tabela FIPE na aba correspondente (API pública Parallelum). Renavam usa dados "
        "simulados até haver provedor configurado.<br/>"
        "<b>Placa com cota gratuita (opcional):</b> serviços como wdapi2, API Placas, FipeAPI Placas e PlacaAPI oferecem "
        "consultas gratuitas diárias mediante cadastro. Crie a constante <code>PLACA_API_URL</code> com a URL do serviço "
        "usando <code>{placa}</code> como marcador (ex.: <code>https://wdapi2.com.br/consulta/{placa}/SUA_CHAVE</code>) e a "
        "consulta por placa passa a retornar dados reais, com valoração FIPE automática.<br/>"
        "<b>Renavam:</b> não há API pública gratuita — o proprietário consulta seus veículos sem custo no "
        "Portal de Serviços Senatran (login gov.br); a API oficial (WSDenatran/Consulta Online Senatran, via SERPRO) "
        "exige termo de autorização no Denatran, e os agregadores da Fase 2 também aceitam Renavam. O app valida o "
        "dígito verificador offline.<br/>"
        "<b>Gráfico de evolução FIPE (opcional):</b> crie a constante <code>FIPE_API_TOKEN</code> com a chave gratuita da "
        "Parallelum (fipe.online) para o gráfico usar o histórico oficial de valores.<br/>"
        "<b>Fase 1 — APIBrasil (pago; consulta por placa):</b> crie uma conta em app.apibrasil.io, ative a "
        "<i>API Placa Dados</i> e, em <b>Workspace settings → Workspace constants</b>, crie a constante "
        "<code>CONSULTA_VEICULAR_API_URL</code> = <code>https://gateway.apibrasil.io/api/v2/vehicles/dados</code> e os secrets "
        "<code>APIBRASIL_BEARER_TOKEN</code> e <code>APIBRASIL_DEVICE_TOKEN</code>.<br/>"
        "<b>Fase 2 — provedor completo (sinistro/leilão):</b> contrate um agregador (Olho no Carro, Checkcred, Consultar Placa etc.), "
        "aponte <code>CONSULTA_VEICULAR_API_URL</code> para o endpoint dele com o secret <code>CONSULTA_VEICULAR_API_KEY</code> "
        "e ajuste o mapeamento na transformação da query <code>consultaProvedor</code>.<br/><br/>"
        "⚖️ Os dados de situação legal têm origem nas bases oficiais (Senatran/Detran, SNG, RENAJUD) intermediadas pelo provedor contratado. "
        "O valor FIPE é obtido da API pública Parallelum quando o código FIPE está disponível. "
        "Este aplicativo tem caráter informativo e não substitui a certidão oficial do Detran."
        "</div>",
        (1, 895, 41, 130),
        (1, 1185, 41, 190),
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
                {"name": "subtipo", "defaultValue": ""},
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
                "renavam: variables.tipoConsulta === 'renavam' ? variables.identificadorConsulta : null, "
                "placa: variables.tipoConsulta === 'placa' ? variables.identificadorConsulta : null, "
                "padraoPlaca: variables.subtipoPlaca || null })}}"
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
        "id": Q_APIBRASIL,
        "name": "consultaApiBrasil",
        "options": {
            "method": "post",
            "url": "{{constants.CONSULTA_VEICULAR_API_URL}}",
            "url_params": [["", ""]],
            "headers": [
                ["Content-Type", "application/json"],
                ["Authorization", "Bearer {{secrets.APIBRASIL_BEARER_TOKEN}}"],
                ["DeviceToken", "{{secrets.APIBRASIL_DEVICE_TOKEN}}"],
            ],
            "body": [["", ""]],
            "json_body": "{{({ placa: variables.identificadorConsulta })}}",
            "body_toggle": True,
            "transformationLanguage": "javascript",
            "enableTransformation": True,
            "transformation": TRANSFORM_APIBRASIL,
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
        "id": Q_DECODE_VIN,
        "name": "decodificarVin",
        "options": {
            "method": "get",
            "url": "{{'https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/' + (variables.identificadorConsulta || '') + '?format=json'}}",
            "url_params": [["", ""]],
            "headers": [["", ""]],
            "body": [["", ""]],
            "json_body": None,
            "body_toggle": False,
            "transformationLanguage": "javascript",
            "enableTransformation": True,
            "transformation": (
                "// Normaliza a resposta do NHTSA vPIC (DecodeVinValues).\n"
                "const linha = (data && data.Results && data.Results[0]) || {};\n"
                "const texto = (v) => (v === undefined || v === null ? '' : String(v).trim());\n"
                "return {\n"
                "  marca: texto(linha.Make),\n"
                "  fabricante: texto(linha.Manufacturer),\n"
                "  modelo: texto(linha.Model),\n"
                "  anoModelo: texto(linha.ModelYear),\n"
                "  paisFabrica: texto(linha.PlantCountry),\n"
                "  tipoVeiculo: texto(linha.VehicleType),\n"
                "  combustivel: texto(linha.FuelTypePrimary),\n"
                "};\n"
            ),
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
        "id": Q_FIPE_MARCAS,
        "name": "fipeMarcas",
        "options": {
            "method": "get",
            "url": "{{'https://parallelum.com.br/fipe/api/v1/' + ((variables.fipeAuto && variables.fipeAuto.tipo) || 'carros') + '/marcas'}}",
            "url_params": [["", ""]],
            "headers": [["", ""]],
            "body": [["", ""]],
            "json_body": None,
            "body_toggle": False,
            "transformationLanguage": "javascript",
            "enableTransformation": False,
            "transformation": None,
            "runOnPageLoad": True,
            "showSuccessNotification": False,
            "notificationDuration": 5000,
        },
        "dataSourceId": DS_RESTAPI,
        "appVersionId": VERSION_ID,
        "createdAt": TS,
        "updatedAt": TS,
    },
    {
        "id": Q_FIPE_MODELOS,
        "name": "fipeModelos",
        "options": {
            "method": "get",
            "url": "{{'https://parallelum.com.br/fipe/api/v1/' + ((variables.fipeAuto && variables.fipeAuto.tipo) || 'carros') + '/marcas/' + ((variables.fipeAuto && variables.fipeAuto.marca) || '') + '/modelos'}}",
            "url_params": [["", ""]],
            "headers": [["", ""]],
            "body": [["", ""]],
            "json_body": None,
            "body_toggle": False,
            "transformationLanguage": "javascript",
            "enableTransformation": True,
            "transformation": "return (data && data.modelos) || [];\n",
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
        "id": Q_FIPE_ANOS,
        "name": "fipeAnos",
        "options": {
            "method": "get",
            "url": "{{'https://parallelum.com.br/fipe/api/v1/' + ((variables.fipeAuto && variables.fipeAuto.tipo) || 'carros') + '/marcas/' + ((variables.fipeAuto && variables.fipeAuto.marca) || '') + '/modelos/' + ((variables.fipeAuto && variables.fipeAuto.modelo) || '') + '/anos'}}",
            "url_params": [["", ""]],
            "headers": [["", ""]],
            "body": [["", ""]],
            "json_body": None,
            "body_toggle": False,
            "transformationLanguage": "javascript",
            "enableTransformation": False,
            "transformation": None,
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
        "id": Q_FIPE_VALOR,
        "name": "fipeValorSelecao",
        "options": {
            "method": "get",
            "url": "{{'https://parallelum.com.br/fipe/api/v1/' + ((variables.fipeAuto && variables.fipeAuto.tipo) || 'carros') + '/marcas/' + ((variables.fipeAuto && variables.fipeAuto.marca) || '') + '/modelos/' + ((variables.fipeAuto && variables.fipeAuto.modelo) || '') + '/anos/' + ((variables.fipeAuto && variables.fipeAuto.ano) || '')}}",
            "url_params": [["", ""]],
            "headers": [["", ""]],
            "body": [["", ""]],
            "json_body": None,
            "body_toggle": False,
            "transformationLanguage": "javascript",
            "enableTransformation": True,
            "transformation": (
                "// Normaliza a resposta da FIPE (Parallelum v1).\n"
                "if (!data || !data.Valor) return null;\n"
                "return {\n"
                "  valor: data.Valor,\n"
                "  marca: data.Marca,\n"
                "  modelo: data.Modelo,\n"
                "  anoModelo: data.AnoModelo,\n"
                "  combustivel: data.Combustivel,\n"
                "  codigoFipe: data.CodigoFipe,\n"
                "  mesReferencia: data.MesReferencia,\n"
                "};\n"
            ),
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
        "id": Q_SEL_MARCA,
        "name": "aoSelecionarMarcaFipe",
        "options": {
            "code": (
                "// Seleção manual de marca: atualiza a fonte de verdade e carrega os modelos.\n"
                "const tipoAtual = String((variables.fipeAuto && variables.fipeAuto.tipo) || components.selectTipoFipe.value || 'carros');\n"
                "await actions.setVariable('fipeAuto', { tipo: tipoAtual, marca: String(components.selectMarcaFipe.value || '') });\n"
                "await queries.fipeModelos.run();\n"
            ),
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
        "id": Q_SEL_MODELO,
        "name": "aoSelecionarModeloFipe",
        "options": {
            "code": (
                "// Seleção manual de modelo: preserva tipo/marca e carrega os anos.\n"
                "const atual = variables.fipeAuto || {};\n"
                "await actions.setVariable('fipeAuto', {\n"
                "  tipo: String(atual.tipo || components.selectTipoFipe.value || 'carros'),\n"
                "  marca: String(atual.marca || components.selectMarcaFipe.value || ''),\n"
                "  modelo: String(components.selectModeloFipe.value || ''),\n"
                "});\n"
                "await queries.fipeAnos.run();\n"
            ),
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
        "id": Q_SEL_ANO,
        "name": "aoSelecionarAnoFipe",
        "options": {
            "code": (
                "// Seleção manual de ano: completa a cadeia, busca o valor oficial e,\n"
                "// havendo FIPE_API_TOKEN, o histórico para o gráfico.\n"
                "const atual = variables.fipeAuto || {};\n"
                "const base = {\n"
                "  tipo: String(atual.tipo || components.selectTipoFipe.value || 'carros'),\n"
                "  marca: String(atual.marca || components.selectMarcaFipe.value || ''),\n"
                "  modelo: String(atual.modelo || components.selectModeloFipe.value || ''),\n"
                "  ano: String(components.selectAnoFipe.value || ''),\n"
                "};\n"
                "await actions.setVariable('fipeAuto', base);\n"
                "await queries.fipeValorSelecao.run();\n"
                "const valorSel = queries.fipeValorSelecao.getData();\n"
                "const temToken = typeof constants !== 'undefined' && constants && constants.FIPE_API_TOKEN;\n"
                "if (temToken && valorSel && valorSel.codigoFipe) {\n"
                "  await actions.setVariable('fipeAuto', Object.assign({}, base, { codigoFipe: String(valorSel.codigoFipe) }));\n"
                "  try { await queries.fipeHistorico.run(); } catch (e) { /* histórico é complementar */ }\n"
                "}\n"
            ),
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
        "id": Q_PLACA_GRATIS,
        "name": "consultaPlacaGratuita",
        "options": {
            "method": "get",
            "url": "{{String(constants.PLACA_API_URL).replace('{placa}', variables.identificadorConsulta)}}",
            "url_params": [["", ""]],
            "headers": [["Accept", "application/json"]],
            "body": [["", ""]],
            "json_body": None,
            "body_toggle": False,
            "transformationLanguage": "javascript",
            "enableTransformation": True,
            "transformation": r"""// Normaliza a resposta de serviços gratuitos de consulta por placa
// (wdapi2, API Placas, FipeAPI Placas, PlacaAPI — formatos semelhantes) para
// o contrato canônico do app.
if (data && (data.error === true || data.erro === true)) {
  throw new Error(data.message || data.mensagem || 'O serviço de placa retornou erro.');
}
// Desembrulha envelopes comuns ({response}/{dados}/{data}) — mas somente
// quando o candidato é um objeto: o wdapi2 tem um campo 'data' que é a data
// da consulta em texto e não pode ser confundido com envelope.
const candidatoRaiz = data && (data.response || data.dados || data.data);
const raiz = (candidatoRaiz && typeof candidatoRaiz === 'object' ? candidatoRaiz : data) || {};
const v = raiz.veiculo || raiz;
const extra = v.extra || raiz.extra || {};
const msg = String(v.mensagemRetorno || raiz.mensagemRetorno || '');
if (/nao encontrado|não encontrado|sem dados/i.test(msg)) {
  throw new Error(msg);
}
const fipeBruto = raiz.fipe && (raiz.fipe.dados || raiz.fipe);
const fipeItem = (Array.isArray(fipeBruto) ? fipeBruto[0] : fipeBruto) || {};

const texto = (valor, padrao) => {
  if (valor === undefined || valor === null || valor === '') return padrao;
  return String(valor).trim();
};

const situacao = texto(v.situacao || extra.situacao_veiculo, '');
const situacaoMin = situacao.toLowerCase();
const codigoSituacao = texto(v.codigoSituacao !== undefined ? v.codigoSituacao : extra.codigoSituacao, '');
let indicadorRouboFurto = null;
if (situacaoMin.indexOf('roubo') !== -1 || situacaoMin.indexOf('furto') !== -1) indicadorRouboFurto = true;
else if (situacaoMin.indexOf('sem restri') !== -1 || situacaoMin.indexOf('circula') !== -1) indicadorRouboFurto = false;
// wdapi2: codigoSituacao "0" = sem ocorrência de roubo/furto na base consultada.
else if (codigoSituacao === '0') indicadorRouboFurto = false;

const restricoes = [];
[v, extra].forEach((origem) => {
  Object.keys(origem || {}).forEach((chave) => {
    if (/^restricao/i.test(chave)) {
      const valor = texto(origem[chave], '');
      if (valor && !/^sem restri/i.test(valor) && valor !== '0') {
        restricoes.push({ tipo: valor, descricao: 'Apontamento retornado pela base consultada.', orgao: '—' });
      }
    }
  });
});

const naoCoberto = 'Não coberto na consulta gratuita';
return {
  veiculo: {
    chassi: texto(v.chassi || extra.chassi, '—'),
    renavam: texto(v.renavam || extra.renavam, '—'),
    placa: texto(v.placa, variables.identificadorConsulta),
    marca: texto(v.marca || v.MARCA || fipeItem.texto_marca, '—'),
    modelo: texto(v.modelo || v.MODELO || v.SUBMODELO || fipeItem.texto_modelo, '—'),
    anoFabricacao: texto(v.ano || v.anoFabricacao || extra.ano_fabricacao, '—'),
    anoModelo: texto(v.anoModelo || v.ano_modelo || extra.ano_modelo || fipeItem.ano_modelo, ''),
    cor: texto(v.cor || extra.cor_veiculo, '—'),
    combustivel: texto(v.combustivel || extra.combustivel || fipeItem.combustivel, '—'),
    codigoCombustivel: null,
    municipio: texto(v.municipio || extra.municipio, '—'),
    uf: texto(v.uf || extra.uf || extra.uf_placa, '—'),
    codigoFipe: texto(fipeItem.codigo_fipe || fipeItem.codigoFipe || v.codigo_fipe, ''),
    procedencia: texto(v.procedencia || extra.procedencia, '—'),
    tipo: texto(v.tipo_veiculo || extra.tipo_veiculo || v.segmento, '—'),
    situacao: texto(situacao, '—'),
  },
  situacaoLegal: {
    status:
      indicadorRouboFurto || restricoes.length > 0
        ? 'Com restrições'
        : indicadorRouboFurto === false
        ? 'Regular'
        : 'Verificação parcial',
    rouboFurto: {
      indicador: indicadorRouboFurto,
      detalhes:
        indicadorRouboFurto === true
          ? 'Constam registros de roubo ou furto na base consultada.'
          : indicadorRouboFurto === false
          ? 'Nada consta na base consultada.'
          : naoCoberto + ' — requer provedor com acesso às bases oficiais.',
    },
    gravame: { status: texto(extra.gravame || v.gravame, naoCoberto), financeira: null, dataInclusao: null },
    debitos: { ipva: naoCoberto, licenciamento: naoCoberto, multas: naoCoberto },
    renajud: naoCoberto,
    restricoes: restricoes,
  },
  sinistros: { indicador: null, ocorrencias: [] },
  leiloes: { indicador: null, ocorrencias: [] },
  fipe: {
    codigoFipe: texto(fipeItem.codigo_fipe || fipeItem.codigoFipe, ''),
    valor: texto(fipeItem.texto_valor || fipeItem.valor, ''),
    mesReferencia: texto(fipeItem.mes_referencia || fipeItem.mesReferencia, ''),
    historico: [],
  },
  metadados: {
    fonte: 'Consulta gratuita de placa (serviço configurado em PLACA_API_URL)',
    modoDemo: false,
    consultadoEm: new Date().toLocaleString('pt-BR'),
  },
};
""",
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
        "id": Q_SEL_TIPO,
        "name": "aoSelecionarTipoFipe",
        "options": {
            "code": (
                "// Troca do segmento (carros/motos/caminhões): reinicia a cadeia e\n"
                "// recarrega as marcas do novo tipo.\n"
                "await actions.setVariable('fipeAuto', { tipo: String(components.selectTipoFipe.value || 'carros') });\n"
                "await queries.fipeMarcas.run();\n"
            ),
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
        "id": Q_FIPE_HIST,
        "name": "fipeHistorico",
        "options": {
            "method": "get",
            "url": (
                "{{'https://parallelum.com.br/fipe/api/v2/' + "
                "({carros: 'cars', motos: 'motorcycles', caminhoes: 'trucks'}[(variables.fipeAuto && variables.fipeAuto.tipo) || 'carros']) + "
                "'/' + ((variables.fipeAuto && variables.fipeAuto.codigoFipe) || '') + "
                "'/years/' + ((variables.fipeAuto && variables.fipeAuto.ano) || '') + '/history'}}"
            ),
            "url_params": [["", ""]],
            "headers": [["X-Subscription-Token", "{{constants.FIPE_API_TOKEN}}"]],
            "body": [["", ""]],
            "json_body": None,
            "body_toggle": False,
            "transformationLanguage": "javascript",
            "enableTransformation": True,
            "transformation": (
                "// Normaliza o histórico de valores da FIPE (Parallelum v2 /history)\n"
                "// para a série usada pelo gráfico: [{ mes, valor }].\n"
                "const lista = (data && (data.priceHistory || data.historico || data.history)) || [];\n"
                "return lista\n"
                "  .map((h) => ({\n"
                "    mes: String(h.month || h.mes || (h.reference && (h.reference.month || h.reference)) || ''),\n"
                "    valor: String(h.price || h.valor || ''),\n"
                "  }))\n"
                "  .filter((h) => h.mes && h.valor)\n"
                "  .reverse();\n"
            ),
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
        "id": Q_LAUDO,
        "name": "gerarLaudoPdf",
        "options": {
            "code": r"""// Gera o laudo veicular em layout A4 e abre o diálogo de impressão do
// navegador (Destino → "Salvar como PDF"). Sem dependências externas.
const r = variables.resultado;
if (!r || !r.veiculo) {
  return null;
}
const esc = (s) =>
  String(s === undefined || s === null || s === '' ? '—' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const indicador = (v, sim, nao, nd) => (v === true ? sim : v === false ? nao : nd);
const corIndicador = (v) => (v === true ? '#b42318' : v === false ? '#027a48' : '#475467');

const v = r.veiculo;
const sl = r.situacaoLegal || {};
const linhasRestricoes = (sl.restricoes || [])
  .map((x) => '<tr><td>' + esc(x.tipo) + '</td><td>' + esc(x.descricao) + '</td><td>' + esc(x.orgao) + '</td></tr>')
  .join('');
const linhasSinistros = ((r.sinistros && r.sinistros.ocorrencias) || [])
  .map((x) => '<tr><td>' + esc(x.data) + '</td><td>' + esc(x.tipo) + '</td><td>' + esc(x.gravidade) + '</td><td>' + esc(x.uf) + '</td><td>' + esc(x.descricao) + '</td></tr>')
  .join('');
const linhasLeiloes = ((r.leiloes && r.leiloes.ocorrencias) || [])
  .map((x) => '<tr><td>' + esc(x.data) + '</td><td>' + esc(x.leiloeiro) + '</td><td>' + esc(x.comitente) + '</td><td>' + esc(x.lote) + '</td><td>' + esc(x.condicao) + '</td><td>' + esc(x.notaAvaliacao) + '</td></tr>')
  .join('');
const linhasHistorico = ((r.fipe && r.fipe.historico) || [])
  .map((h) => '<tr><td>' + esc(h.mes) + '</td><td style="text-align:right">' + esc(h.valor) + '</td></tr>')
  .join('');

const campo = (rotulo, valor) =>
  '<div class="campo"><div class="rotulo">' + rotulo + '</div><div class="valor">' + esc(valor) + '</div></div>';

const html = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"/>' +
  '<title>Laudo de Consulta Veicular — ' + esc(v.placa !== '—' ? v.placa : v.chassi) + '</title>' +
  '<style>' +
  '@page { size: A4; margin: 16mm 14mm; }' +
  '* { box-sizing: border-box; } body { font-family: Arial, Helvetica, sans-serif; color: #1b1f31; margin: 0; font-size: 12px; }' +
  '.cabecalho { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 3px solid #3e63dd; padding-bottom: 10px; }' +
  '.titulo { font-size: 22px; font-weight: 800; } .subtitulo { color: #687076; margin-top: 2px; }' +
  '.meta { text-align: right; color: #475467; font-size: 11px; line-height: 1.6; }' +
  'h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .06em; color: #3e63dd; border-bottom: 1px solid #e6e8eb; padding-bottom: 4px; margin: 18px 0 8px; }' +
  '.grade { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px 14px; }' +
  '.campo .rotulo { font-size: 9px; text-transform: uppercase; color: #687076; letter-spacing: .05em; }' +
  '.campo .valor { font-weight: 700; margin-top: 1px; }' +
  '.selo { display: inline-block; padding: 3px 10px; border-radius: 12px; font-weight: 700; font-size: 12px; }' +
  'table { width: 100%; border-collapse: collapse; margin-top: 4px; } th { text-align: left; font-size: 10px; text-transform: uppercase; color: #687076; }' +
  'th, td { border-bottom: 1px solid #edeff5; padding: 5px 6px; vertical-align: top; }' +
  '.aviso { margin-top: 22px; padding: 10px 12px; background: #f8f9fc; border: 1px solid #e6e8eb; border-radius: 6px; color: #475467; font-size: 10px; line-height: 1.6; }' +
  '.fipe-destaque { font-size: 20px; font-weight: 800; color: #1d4ed8; }' +
  '</style></head><body>' +
  '<div class="cabecalho"><div><div class="titulo">🚗 Laudo de Consulta Veicular</div>' +
  '<div class="subtitulo">Consulta Veicular Brasil — relatório informativo</div></div>' +
  '<div class="meta">Emitido em: ' + esc(new Date().toLocaleString('pt-BR')) + '<br/>' +
  'Identificador consultado: <b>' + esc(variables.identificadorConsulta) + '</b><br/>' +
  'Fonte: ' + esc(r.metadados && r.metadados.fonte) + '</div></div>' +

  '<h2>Dados do veículo</h2><div class="grade">' +
  campo('Marca', v.marca) + campo('Modelo', v.modelo) + campo('Ano fabricação/modelo', esc(v.anoFabricacao) + '/' + esc(v.anoModelo)) + campo('Cor', v.cor) +
  campo('Placa', v.placa) + campo('Chassi', v.chassi) + campo('Renavam', v.renavam) + campo('Combustível', v.combustivel) +
  campo('Município/UF', esc(v.municipio) + '/' + esc(v.uf)) + campo('Procedência', v.procedencia) + campo('Tipo', v.tipo) + campo('Código FIPE', v.codigoFipe || '—') +
  '</div>' +

  '<h2>Situação legal</h2>' +
  '<p>Status geral: <span class="selo" style="background:#f2f4f7;color:' +
  (sl.status === 'Regular' ? '#027a48' : sl.status === 'Com restrições' ? '#b54708' : sl.status === 'Alerta' ? '#b42318' : '#475467') + '">' + esc(sl.status) + '</span></p>' +
  '<div class="grade">' +
  '<div class="campo"><div class="rotulo">Roubo / Furto</div><div class="valor" style="color:' + corIndicador(sl.rouboFurto && sl.rouboFurto.indicador) + '">' +
  indicador(sl.rouboFurto && sl.rouboFurto.indicador, 'Consta ocorrência', 'Nada consta', 'Não verificado') + '</div></div>' +
  campo('Gravame (SNG)', sl.gravame && sl.gravame.status) + campo('RENAJUD', sl.renajud) +
  campo('IPVA', sl.debitos && sl.debitos.ipva) + campo('Licenciamento', sl.debitos && sl.debitos.licenciamento) + campo('Multas', sl.debitos && sl.debitos.multas) +
  '</div>' +
  (linhasRestricoes
    ? '<h2>Restrições registradas</h2><table><tr><th>Tipo</th><th>Descrição</th><th>Órgão</th></tr>' + linhasRestricoes + '</table>'
    : '') +

  '<h2>Sinistros</h2><p style="color:' + corIndicador(r.sinistros && r.sinistros.indicador) + ';font-weight:700">' +
  indicador(r.sinistros && r.sinistros.indicador, 'Constam registros de sinistro.', 'Nada consta.', 'Não coberto pela fonte consultada.') + '</p>' +
  (linhasSinistros
    ? '<table><tr><th>Data</th><th>Tipo</th><th>Gravidade</th><th>UF</th><th>Descrição</th></tr>' + linhasSinistros + '</table>'
    : '') +

  '<h2>Leilões</h2><p style="color:' + corIndicador(r.leiloes && r.leiloes.indicador) + ';font-weight:700">' +
  indicador(r.leiloes && r.leiloes.indicador, 'Consta passagem por leilão.', 'Nada consta.', 'Não coberto pela fonte consultada.') + '</p>' +
  (linhasLeiloes
    ? '<table><tr><th>Data</th><th>Leiloeiro</th><th>Comitente</th><th>Lote</th><th>Condição</th><th>Nota</th></tr>' + linhasLeiloes + '</table>'
    : '') +

  '<h2>Avaliação FIPE</h2>' +
  (r.fipe && r.fipe.valor
    ? '<p><span class="fipe-destaque">' + esc(r.fipe.valor) + '</span> &nbsp; <span style="color:#687076">Código FIPE ' +
      esc(r.fipe.codigoFipe) + ' • Referência: ' + esc(r.fipe.mesReferencia) + '</span></p>'
    : '<p style="color:#687076">Valor de referência não disponível para esta consulta.</p>') +
  (linhasHistorico
    ? '<table style="max-width:70%"><tr><th>Mês de referência</th><th style="text-align:right">Valor</th></tr>' + linhasHistorico + '</table>'
    : '') +

  '<div class="aviso"><b>Aviso legal:</b> este laudo tem caráter meramente informativo e reflete as fontes indicadas na data de emissão. ' +
  'Não substitui a certidão oficial do Detran do estado de registro do veículo nem laudos de vistoria presencial. ' +
  'Itens marcados como "não verificado" ou "não coberto" exigem consulta a provedor com acesso às bases correspondentes.</div>' +
  '</body></html>';

const janela = window.open('', '_blank');
if (!janela) {
  throw new Error('O navegador bloqueou a janela do laudo. Permita pop-ups para este endereço e tente novamente.');
}
janela.document.write(html);
janela.document.close();
janela.focus();
setTimeout(() => { try { janela.print(); } catch (e) {} }, 400);
return { gerado: true };
""",
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
        "id": uid("event-tipo-fipe"),
        "name": "onSelect",
        "index": 0,
        "event": {
            "eventId": "onSelect",
            "actionId": "run-query",
            "queryId": Q_SEL_TIPO,
            "queryName": "aoSelecionarTipoFipe",
            "parameters": {},
        },
        "sourceId": COMP_BY_NAME["selectTipoFipe"]["id"],
        "target": "component",
        "appVersionId": VERSION_ID,
        "createdAt": TS,
        "updatedAt": TS,
    },
    {
        "id": uid("event-botao-laudo"),
        "name": "onClick",
        "index": 0,
        "event": {
            "eventId": "onClick",
            "actionId": "run-query",
            "queryId": Q_LAUDO,
            "queryName": "gerarLaudoPdf",
            "parameters": {},
        },
        "sourceId": COMP_BY_NAME["botaoLaudo"]["id"],
        "target": "component",
        "appVersionId": VERSION_ID,
        "createdAt": TS,
        "updatedAt": TS,
    },
    {
        "id": uid("event-marca-fipe"),
        "name": "onSelect",
        "index": 0,
        "event": {
            "eventId": "onSelect",
            "actionId": "run-query",
            "queryId": Q_SEL_MARCA,
            "queryName": "aoSelecionarMarcaFipe",
            "parameters": {},
        },
        "sourceId": COMP_BY_NAME["selectMarcaFipe"]["id"],
        "target": "component",
        "appVersionId": VERSION_ID,
        "createdAt": TS,
        "updatedAt": TS,
    },
    {
        "id": uid("event-modelo-fipe"),
        "name": "onSelect",
        "index": 0,
        "event": {
            "eventId": "onSelect",
            "actionId": "run-query",
            "queryId": Q_SEL_MODELO,
            "queryName": "aoSelecionarModeloFipe",
            "parameters": {},
        },
        "sourceId": COMP_BY_NAME["selectModeloFipe"]["id"],
        "target": "component",
        "appVersionId": VERSION_ID,
        "createdAt": TS,
        "updatedAt": TS,
    },
    {
        "id": uid("event-ano-fipe"),
        "name": "onSelect",
        "index": 0,
        "event": {
            "eventId": "onSelect",
            "actionId": "run-query",
            "queryId": Q_SEL_ANO,
            "queryName": "aoSelecionarAnoFipe",
            "parameters": {},
        },
        "sourceId": COMP_BY_NAME["selectAnoFipe"]["id"],
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
    "description": "Consulte a situação completa de um veículo brasileiro a partir do chassi/VIN, do Renavam ou da placa (antiga ou Mercosul): dados cadastrais, situação legal (roubo/furto, gravame, RENAJUD, débitos), sinistros, leilões e valor de referência na tabela FIPE.",
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
